import numpy as np
import pandas as pd
import sklearn.base
import sklearn.utils

from sklearn.utils.validation import check_is_fitted

import logging
logger = logging.getLogger(__name__)

class NaNLabelEncoder(sklearn.base.BaseEstimator, sklearn.base.TransformerMixin):
    """ A label encoder which handles missing values

    In the data, `np.nan` will be taken as a missing value.

    Parameters
    ----------
    missing_value_marker: string
        A flag value which will be used internally for missing values. This
        value should not appear in the actual data.

    labels: list-like of values
        Optionally, a list of values can be given; any values which do not
        appear in the training data, but present in the list, will still be
        accounted for.

    treat_unknown_as_missing: bool
        By default, `transform` will fail when attempting to encode a value
        not seen during fitting. If this flag is `True`, then unknown values
        will instead be replaced with np.nan during `transform`.
    """
    def __init__(self, missing_value_marker='---NaN---', labels=None,
            treat_unknown_as_missing=False):
        self.missing_value_marker = missing_value_marker
        self.labels = labels
        self.treat_unknown_as_missing = treat_unknown_as_missing
        

    def fit(self, y):
        """Fit label encoder
        Parameters
        ----------
        y : array-like of shape (n_samples,)
            Target values.
        Returns
        -------
        self : returns an instance of self.
        """
        # we cannot use np.nan as the missing value marker
        if pd.isnull(self.missing_value_marker):
            msg = ("[nan_label_encoder]: cannot use pd.isnull objects as the "
                "internal missing value marker")
            raise ValueError(msg)

        y = sklearn.utils.column_or_1d(y, warn=False)

        if self.missing_value_marker in y:
            msg = ("[nan_label_encoder]: found the missing value marker in "
                "the array")
            raise ValueError(msg)

        y = y.copy()

        # use our marker for any NaNs
        m_nan = pd.isnull(y)
        self.classes_ = np.unique(y[~m_nan])

        # and make sure to include the labels we specified
        if self.labels is not None:
            self.classes_ = np.unique(list(self.classes_) + self.labels)

        # update the labels to reflect the classes in the data, plus the labels
        # that we specified
        self.labels = self.classes_
        
        # add our missing value marker to the end
        self.classes_ = np.append(self.classes_, [self.missing_value_marker])

        return self

    def get_num_classes(self):
        """ The number of classes, not including the missing value marker
        """
        return len(self.labels)

    def transform(self, y):
        """Transform labels to normalized encoding.
        Parameters
        ----------
        y : array-like of shape [n_samples]
            Target values.
        Returns
        -------
        y : array-like of shape [n_samples]
        """
        check_is_fitted(self, 'classes_')
        y = sklearn.utils.column_or_1d(y, warn=True)
        y = np.array(y, dtype=object)

        # use our marker for NaNs
        m_nan = pd.isnull(y)

        if self.treat_unknown_as_missing:
            m_known = np.isin(y, self.classes_)
            m_nan |= ~m_known

        y[m_nan] = self.missing_value_marker
    
        # then make sure we know all of the labels

        classes = np.unique(y)
        msg = ("[nan_label_encoder.transform] classes: {}. self.classes_: {}".
            format(classes, self.classes_))
        logger.debug(msg)
        if len(np.intersect1d(classes, self.classes_)) < len(classes):
            diff = np.setdiff1d(classes, self.classes_)
            raise ValueError("y contains new labels: %s" % str(diff))


        # however, put the NaNs back in
        ret = np.searchsorted(self.classes_, y).astype(float)
        ret[m_nan] = np.nan
        return ret

    def inverse_transform(self, y):
        """Transform labels back to original encoding.
        Parameters
        ----------
        y : numpy array of shape [n_samples]
            Encoded target values. That is, these should be integers in
            the range [0, n_classes].
        Returns
        -------
        y : numpy array of shape [n_samples]
        """
        check_is_fitted(self, 'classes_')

        # mark the nan's
        m_nan = pd.isnull(y)
        y[m_nan] = len(self.classes_)-1

        diff = np.setdiff1d(y[~m_nan], np.arange(len(self.classes_), dtype=object))
        if diff:
            raise ValueError("y contains new labels: {}".format(str(diff)))

        y = np.asarray(y, dtype=int)
        return self.classes_[y]
