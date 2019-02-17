import pickle
from typing import Optional

import numpy as np

from ..typedefs.classifiers import DataDict
from ..typedefs.extraction import ActivationRanges
from ..typedefs.models import ActivationName
from ..utils.paths import load_pickle, trim


class ActivationReader:
    """ Reads in pickled activations that have been extracted.

    Parameters
    ----------
    activations_dir : str
        Directory containing the extracted activations
    label_path : str, optional
        Path to pickle file containing the labels. Defaults to
        labels.pickle in activations_dir if no path has been provided.

    Attributes
    ----------
    activations_dir : str
    _labels : np.ndarray
        Numpy array containing the extracted labels
    _data_len : int
        Number of extracted activations
    """
    def __init__(self,
                 activations_dir: str,
                 label_path: Optional[str] = None) -> None:

        self.activations_dir = trim(activations_dir)

        if label_path is None:
            label_path = f'{self.activations_dir}/labels.pickle'
        self.label_path = label_path

        self._labels: Optional[np.ndarray] = None
        self._data_len: int = -1
        self._activations: Optional[np.ndarray] = None
        self._activation_ranges: Optional[ActivationRanges] = None

    def __getitem__(self, item: int) -> np.ndarray:
        assert self.activations is not None, 'self.activations should be set first'
        assert item in self.activation_ranges, 'key not present in activation ranges dict'

        min_ind, max_ind = self.activation_ranges[item]
        return self.activations[min_ind:max_ind]

    @property
    def labels(self) -> np.ndarray:
        if self._labels is None:
            self._labels = load_pickle(self.label_path)
        return self._labels

    @property
    def data_len(self) -> int:
        if self._data_len == -1:
            self._data_len = len(self.labels)
        return self._data_len

    @property
    def activation_ranges(self) -> ActivationRanges:
        if self._activation_ranges is None:
            self._activation_ranges = load_pickle(f'{self.activations_dir}/ranges.pickle')
        return self._activation_ranges

    @property
    def activations(self) -> Optional[np.ndarray]:
        return self._activations

    @activations.setter
    def activations(self, activation_name: ActivationName) -> None:
        self._activations = self.read_activations(activation_name)

    def read_activations(self, activation_name: ActivationName) -> np.ndarray:
        """ Reads the pickled activations of activation_name
        
        Parameters
        ----------
        activation_name : ActivationName
            (layer, name) tuple indicating the activations to be read in
        
        Returns
        -------
        activations : np.ndarray
            Numpy array of activation values
        """
        l, name = activation_name
        filename = f'{name}_l{l}.pickle'

        hidden_size = None
        activations = None

        n = 0

        # The activations can be stored as a series of pickle dumps, and
        # are therefore loaded until an EOFError is raised.
        with open(f'{self.activations_dir}/{filename}', 'rb') as f:
            while True:
                try:
                    sen_activations = pickle.load(f)

                    # To make hidden size dependent of data only, the activations array
                    # is created only after observing the first batch of activations.
                    # TODO: Take care of data_len when using unlabeled corpora! (use np.concatenate)
                    if hidden_size is None:
                        hidden_size = sen_activations.shape[1]
                        activations = np.empty((self.data_len, hidden_size), dtype=np.float32)

                    i = len(sen_activations)
                    activations[n:n+i] = sen_activations
                    n += i
                except EOFError:
                    break

        return activations

    def create_data_split(self,
                          activation_name: ActivationName,
                          data_subset_size: int = -1,
                          train_test_split: float = 0.9) -> DataDict:
        """ Creates train/test data split of activations

        Parameters
        ----------
        activation_name : ActivationName
            (layer, name) tuple indicating the activations to be read in
        data_subset_size : int, optional
            Subset size of data to train on. Defaults to -1, indicating
            the entire data set.
        train_test_split : float
            Percentage of the train/test split. Defaults to 0.9.
        """

        if data_subset_size != -1:
            assert 0 < data_subset_size <= self.data_len, \
                "Size of subset must be positive and not bigger than the whole data set."

        activations = self.read_activations(activation_name)

        data_size = self.data_len if data_subset_size == -1 else data_subset_size
        split = int(data_size * train_test_split)

        indices = np.random.choice(range(data_size), data_size, replace=False)
        train_indices = indices[:split]
        test_indices = indices[split:]

        return {
            'train_x': activations[train_indices],
            'train_y': self.labels[train_indices],
            'test_x': activations[test_indices],
            'test_y': self.labels[test_indices]
        }
