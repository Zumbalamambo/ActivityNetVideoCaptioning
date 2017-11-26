import os
import json
import numpy as np
import cPickle as pickle
from sklearn.preprocessing import normalize


class DataManager:
    """
    This class manages the captions of frames of all videos.
    It also provides functions for nearest neighbor search.
    """
    def __init__(self):
        # mapping from (video_name, segment_id) to caption
        self.video_seg_id_to_caption = {}

        # mapping from (video segment name, frame_idx) to frame path
        self.video_seg_frame_path = {}

        # features
        self.features = []

        # captions associated with each feature
        self.captions = []

        # all captions appeared
        self.raw_captions = []

        # path to frames
        self.frame_paths = []

        # mapping from video segment name to feature file.
        self.video_seg_feature_path = {}

        # mapping from video segment name to key frames
        self.key_frames = {}

    def load_frame_path_info(self, frame_folder):
        print('loading frame path info...')
        for root, _, files in os.walk(frame_folder):
            for file in sorted(files):
                # skip non-jpeg files
                if not file.endswith('.jpg'):
                    continue
                file_path = os.path.join(root, file)
                video_segment_name = file_path.split('/')[-2]
                frame_number = int(file.split('.')[0])-1
                self.video_seg_frame_path[(video_segment_name, frame_number)] = file_path

    def load_captions(self, caption_file):
        print('loading captions...')
        file = open(caption_file, 'r')
        database = json.load(open(caption_file, 'r'))
        for video_name in database.keys():
            data = database[video_name]
            sentences = data['sentences']
            self.raw_captions.extend(sentences)
            for seg_id in range(len(sentences)):
                self.video_seg_id_to_caption[(video_name, seg_id)] = sentences[seg_id]
        file.close()

    def load_key_frame_information(self, keyframe_info_folder):
        print('loading key frame information...')
        for root, _, files in os.walk(keyframe_info_folder):
            for file in sorted(files):
                # skip non-txt files
                if not file.endswith('.txt'):
                    continue
                file_path = os.path.join(root, file)
                video_segment_name = file[:-4]
                assert len(video_segment_name) >= 14
                data = np.int32(np.loadtxt(file_path))
                if type(data) is not np.ndarray:
                    data = np.array([data])
                key_frames = set(np.int32(data))
                self.key_frames[video_segment_name] = key_frames

    def load_features(self, feature_folder):
        for root, folder, files in os.walk(feature_folder):
            print('loading features from %s...' % root)
            for file in sorted(files):
                # skip non-txt files
                if not file.endswith('.txt'):
                    continue
                file_path = os.path.join(root, file)
                # extract video name and segment id from file name
                video_segment_name = file[:-4]
                assert len(video_segment_name) >= 14
                video_name = video_segment_name[:13]
                segment_id = int(video_segment_name[13:])
                self.video_seg_feature_path[video_segment_name] = file_path
                caption = self.video_seg_id_to_caption[(video_name, segment_id)]
                f = open(file_path, 'r')
                count = 0
                key_frames = self.key_frames[video_segment_name]
                for line in f:
                    if count in key_frames:
                        feature = line.strip().split(',')
                        feature = np.array([float(item) for item in feature])
                        self.features.append(feature)
                        self.captions.append(caption)
                        self.frame_paths.append(self.video_seg_frame_path[video_segment_name, count])
                    count += 1
        self.features = np.array(self.features)
        print('features for %d frames are loaded.' % len(self.features))

    def normalize_features(self):
        print('normalizing features...')
        self.features = normalize(self.features, axis=1)

    def query_knn_caption_brutal_force_cosine_similarity(self, query_feature, k):
        k_max_similarities = np.array([-1.] * k)
        k_best_indices = np.array([-1] * k)
        query_feature = normalize(query_feature)[0]
        for i, feature in enumerate(self.features):
            similarity = np.dot(feature, query_feature)
            assert similarity >= -1.01
            assert similarity <= 1.01
            idx_min = np.argmin(k_max_similarities)
            if similarity > k_max_similarities[idx_min]:
                k_max_similarities[idx_min] = similarity
                k_best_indices[idx_min] = i
        args_sort = np.argsort(k_max_similarities)[::-1]
        k_max_similarities = k_max_similarities[args_sort]
        k_best_indices = k_best_indices[args_sort]
        captions = [self.captions[idx] for idx in k_best_indices]
        frame_paths = [self.frame_paths[idx] for idx in k_best_indices]
        return captions, frame_paths, k_max_similarities

    def query_knn_caption_brutal_force_euclidean_distance(self, query_feature, k):
        k_min_distances = np.array([np.inf] * k)
        k_best_indices = np.array([-1] * k)
        for i, feature in enumerate(self.features):
            distance = np.linalg.norm(feature - query_feature)
            idx_max = np.argmax(k_min_distances)
            if distance < k_min_distances[idx_max]:
                k_min_distances[idx_max] = distance
                k_best_indices[idx_max] = i
        args_sort = np.argsort(k_min_distances)
        k_min_distances = k_min_distances[args_sort]
        k_best_indices = k_best_indices[args_sort]
        captions = [self.captions[idx] for idx in k_best_indices]
        frame_paths = [self.frame_paths[idx] for idx in k_best_indices]
        return captions, frame_paths, k_min_distances

    def get_frames_path(self, video_segment_name):
        key_frames = list(self.key_frames[video_segment_name])
        return [self.video_seg_frame_path[(video_segment_name, key_frame)] for key_frame in key_frames]

    def get_frames_features(self, video_segment_name):
        key_frames = self.key_frames[video_segment_name]
        feature_file = self.video_seg_feature_path[video_segment_name]
        f = open(feature_file, 'r')
        frame_features = []
        count = 0
        for line in f:
            if count in key_frames:
                fields = line.strip().split(',')
                fields = [float(field) for field in fields]
                frame_features.append(np.array(fields))
            count += 1
        frame_features = np.array(frame_features)
        return frame_features

    def get_video_segment_caption(self, video_segment_name):
        return self.video_seg_id_to_caption[(video_segment_name[:13], int(video_segment_name[13:]))]

    def save(self, save_path):
        print('saving data manager...')
        file = open(save_path, 'wb')
        data = (self.video_seg_id_to_caption,
                self.video_seg_frame_path,
                self.features,
                self.captions,
                self.raw_captions,
                self.frame_paths,
                self.video_seg_feature_path,
                self.key_frames)
        pickle.dump(data, file)
        file.close()

    def load(self, load_path):
        print('loading data manager...')
        file = open(load_path, 'rb')
        (self.video_seg_id_to_caption,
         self.video_seg_frame_path,
         self.features,
         self.captions,
         self.raw_captions,
         self.frame_paths,
         self.video_seg_feature_path,
         self.key_frames) = pickle.load(file)
        file.close()
