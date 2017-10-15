"""
This module contains utilities for removing data according to different
missingness mechanisms, including missing at random (MAR), missing completely
at random (MCAR), and not missing at random (NMAR).

Example::

    import functools
    import numpy as np
    import sklearn.datasets
    import misc.missing_data_utils as missing_data_utils
    
    X_complete, y = sklearn.datasets.load_iris(return_X_y=True)

    # mcar

    # all observations have a 20% chance of being missing
    missing_likelihood = 0.2
    X_mcar_incomplete = missing_data_utils.get_mcar_incomplete_data(
        X_complete,
        missing_likelihood
    )

    # nmar

    # remove all `x[1]` values greater than 4
    # and all `x[3]` values greater than 0.3
    missing_likelihood = [
        None,
        functools.partial(remove_large_values, threshold=4),
        None,
        functools.partial(remove_large_values, threshold=0.3)
    ]

    X_nmar_incomplete = missing_data_utils.get_nmar_incomplete_data(
        X_complete,
        missing_likelihood
    )

    # mar

    # remove `x[3]` when `x[0]*x[1] > 18`
    missing_likelihood = functools.partial(
        missing_data_utils.remove_y_when_z_is_large,
        y=3, z=[0,1], threshold=18, combination_operator=np.product
    )
    X_mar_incomplete = missing_data_utils.get_mar_incomplete_data(
        X_complete,
        missing_likelihood
    )

    # get training, testing splits suitable for use in sklearn
    mcar_data = missing_data_utils.get_incomplete_data_splits(
        X_complete,
        X_mcar_incomplete,
        y
    )
    nmar_data = missing_data_utils.get_incomplete_data_splits(
        X_complete,
        X_mcar_incomplete,
        y
    )
    mar_data = missing_data_utils.get_incomplete_data_splits(
        X_complete,
        X_mcar_incomplete,
        y
    )
"""

import collections
import numpy as np
import sklearn.model_selection

import misc.math_utils as math_utils
import more_itertools

###
#   Functions for creating incomplete datasets according to different
#   missingness mechanisms
###

def get_mcar_incomplete_data(X, missing_likelihood=0.1, random_state=8675309):
    """ Remove some of the observations
    
    Internally, this function uses an MCAR mechanism to remove the data. That
    is, the likelihood that an opbservation is independent of both the value
    itself and other values in the rows.
    
    Parameters
    ----------
    X: data matrix
        A data matrix suitable for sklearn
        
    missing_likelihood: float
        The likelihood each observation in the training data will be missing
        
    random_state: int
        An attempt to make things reproducible
        
    Returns
    -------
    X_incomplete: data matrix
        The incomplete training data for this fold
    """
    
    X_incomplete, missing_mask = math_utils.mask_random_values(
        X,
        likelihood=missing_likelihood,
        return_mask=True,
        random_state=random_state
    )
    
    return X_incomplete


def get_nmar_incomplete_data(X, missing_likelihood=None, random_state=8675309):
    """ Remove some of the observations
    
    Internally, this function uses an NMAR mechanism. That is, the likelihood
    that an observation is missing depends on the value.    
    Parameters
    ----------
    X: data matrix
        A data matrix suitable for sklearn
        
    missing_likelihood: list of callables
        Callables which determine whether a given feature observation
        is missing, giving the value of that feature. The indices within the
        list should match the columns in `X`.

        Specifically, the callables should take as input a 1D `np.array` of
        floats and return a 1D `np.array` of floats with the same shape. The
        array gives all values for the respective feature. See
        `remove_large_values` for a simple example.
        
        `None`s can be given if all observations for the respective feature
        are present.
        
    random_state: int
        An attempt to make things reproducible
        
    Returns
    -------
    X_incomplete: data matrix
        The incomplete data matrix
    """
    np.random.seed(random_state)

    # make sure we have an appropriate number of functions
    if len(missing_likelihood) != X.shape[1]:
        msg = ("[get_nmar_complete_data]: the number of functions for "
            "missing data does not match the number of dimensions of the "
            "data.")
        raise ValueError(msg)
    
    X_ret = X.copy()
    
    for i in range(X.shape[1]):
        if not missing_likelihood[i] is None:
            X_ret[:,i] = missing_likelihood[i](X[:,i])

    return X_ret

def remove_large_values(X, threshold, return_mask=False):
    """ Remove values above the threshold in `X`

    This function is suitable for use with `get_nmar_incomplete_data`.
    
    All of the shapes are the same as X.
    
    Parameters
    ----------
    X: np.array of floats
        The values
        
    threshold: float
        The threshold to remove values
        
    Returns
    -------
    X_masked: np.array of floats
        A copy of the input array, with the large values replaced with
        np.nan.
        
    mask: np.array of bools
        A mask of the high values which were removed. Returned only if
        `return_mask` was True
    """
    X_small = X.copy()
    
    m = X > threshold
    X_small[m] = np.nan
    
    ret = X_small 
    if return_mask:
        ret = ret, m
        
    return ret


def get_mar_incomplete_data(X, missing_likelihood=None, random_state=8675309):
    """ Remove some of the observations
    
    Internally, this function uses an MAR mechanism. That is, the likelihood
    that an observation is missing depends on the other values in that
    instance.

    Parameters
    ----------
    X: data matrix
        A data matrix suitable for sklearn
        
    missing_likelihood: callable
        A callable which determines the missing values for an instance
        `x`. The callable should take one argument: `x`, the instance,
        and it should return a copy with missing values replaced with `np.nan`.
        
    random_state: int
        An attempt to make things reproducible
        
    Returns
    -------
    X_incomplete: data matrix
        The incomplete data matrix
    """
    np.random.seed(random_state)
    X_ret = np.full_like(X, np.nan)
    
    # determine the missingness patterns in each row
    for i in range(X.shape[0]):
        X_ret[i] = missing_likelihood(X[i])

    return X_ret

def remove_y_when_z_is_large(x, y, z, threshold,
        combination_operator=np.product):
    """ Remove values of `y` when the combined values of `z` exceed `threshold`

    This function is suitable for use with `get_mar_incomplete_data`.
    
    Parameters
    ----------
    x: 1D `np.array` of floats
        The instance
        
    y: int
        The index of the value to consider removing
        
    z: int or iterable of ints
        The indices of the "condition" values
        
    threshold: float
        The threshold to consider a combined value as "large"
        
    combination_operator: callable with one parameter
        The operation to combine the `z` variables. The callable should take
        an array of size |z|. 
        
    Returns
    -------
    x_missing: 1D np.array of floats
        A copy of `x` with the value at index `y` replaced with `np.nan` if
        appropriate based on the combined values of `z` and `threshold`.
    """
    val = combination_operator(x[z])
    
    x_missing = np.copy(x)
    if val > threshold:
        x_missing[y] = np.nan
        
    return x_missing

def get_incomplete_data(X, mechanism, missing_likelihood, random_state=8675309):
    """ Remove some observations according to the specified missing  mechanism

    This is a simple wrapper around the respective functions. In principle, it
    provides a consistent interface for all of them.

    Parameters
    ----------
    X: data matrix
        A data matrix suitable for sklearn

    mechanism: string in "mcar", "mar", "nmar" (case-insensitive)
        The missing data mechanism to use
        
    missing_likelihood: object
        The `missing_likelihood` parameter for the respective
        `get_XXX_incomplete_data` functions. Please see the documentation for
        those functions for more details.

    random_state: int
        An attempt to make things reproducible

    Returns
    -------
    X_incomplete: data matrix
        The incomplete data matrix
    """

    mechanism = mechanims.lower()

    if mechanism == "mcar":
        X_incomplete = get_mcar_incomplete_data(X, missing_likelihood, random_state)
    elif mechanism == "mar":
        X_incomplete = get_mar_incomplete_data(X, missing_likelihood, random_state)
    elif mechanism == "nmar":
        X_incomplete = get_nmar_incomplete_data(X, missing_likelihood, random_state)
    else:
        valid_mechanisms = ["mcar", "mar", "nmar"]
        valid_mechanisms = ' '.join(valid_mechanisms)
        msg = ("[get_incomplete_data]: unknown missing data mechansim: {}. Must "
            "be one of: {}".format(mechanism, valid_mechanisms))
        raise ValueError(msg)
        
    return X_incomplete


###
#   Helpers for evaluation with incomplete datasets
###

_incomplete_dataset_fields = (
    "X_train_complete",
    "X_train_incomplete",
    "X_test_complete",
    "X_test_incomplete",
    "y_train",
    "y_test"
)
_incomplete_dataset_fields = ' '.join(_incomplete_dataset_fields)
IncompleteDataset = collections.namedtuple(
    "IncompleteDataset",
    _incomplete_dataset_fields
)

def get_incomplete_data_splits(
        X_complete,
        X_incomplete,
        y,
        fold=0,
        num_folds=10,
        random_state=8675309):

    """ Split the datasets using StratifiedKFold cross-validation
    
    Parameters
    ----------
    X_complete: data matrix
        A data matrix suitable for sklearn, without missing values
        
    X_incomplete: data matrix
        A data matrix suitable for sklearn, with missing values represented as np.nan
        
    y: target variables
        The target variables corresponding to X
        
    fold: int
        The cv fold to return
        
    num_folds: int
        The number of cv folds to create
        
    random_state: int
        An attempt to make things reproducible
        
    Returns (as a named tuple)
    -------
    X_train_complete: data matrix
        The complete training data for this fold
        
    X_train_incomplete: data matrix
        The incomplete training data for this fold
        
    X_test_complete: data matrix
        The complete testing data for this fold
        
    X_test_incomplete: data matrix
        The incomplete testing data for this fold
        
    y_train: target variables
        The (complete) training target data for this fold
        
    y_test: target variables
        The (complete) testing target data for this fold
    """
    
    
    cv = sklearn.model_selection.StratifiedKFold(
        num_folds, random_state=random_state
    )

    splits = cv.split(X_complete, y)
    train, test = more_itertools.nth(splits, fold)

    X_train_complete, y_train = X_complete[train], y[train]
    X_test_complete, y_test = X_complete[test], y[test]
    
    X_train_incomplete = X_incomplete[train]
    X_test_incomplete = X_incomplete[test]

    ret = IncompleteDataset(
        X_train_complete,
        X_train_incomplete,
        X_test_complete,
        X_test_incomplete,
        y_train,
        y_test
    )
    
    return ret
    
_training_results_fields = (
    "model_fit_c",
    "model_fit_i",
    "y_pred_cc",
    "y_pred_ic",
    "y_pred_ci",
    "y_pred_ii",
    "y_test"
)
_training_results_fields = ' '.join(_training_results_fields)
TrainingResults = collections.namedtuple(
    "TrainingResults",
    _training_results_fields
)

def train_on_incomplete_data(model, incomplete_data):
    """ Perform all combinations of training and testing for the model and
    incomplete data set structure.
    
    In particular, this function fits the model using both the complete and
    incomplete versions of the data. It then makes predictions on both the 
    complete and incomplete versions of the test data.
    
    Parameters
    ----------
    model: an sklearn model
        In particular, the model must support cloning via `sklearn.clone`,
        have a `fit` method and have a `predict` method after fitting.
        
    incomplete_data: an IncompleteData named tuple
        A structure containing both complete and incomplete data. Presumably,
        this was created using `get_incomplete_data_splits`.
    
    Returns (as a named tuple)
    -------
    model_fit_c: fit sklearn model
        The model fit using the complete data
        
    model_fit_i: fit sklearn model
        The model fit using the incomplete data
        
    y_pred_cc: np.array
        The predictions from `model_fit_c` on the complete test dataset
        
    y_pred_ci: np.array
        The predictions from `model_fit_c` on the incomplete test data
        
    y_pred_ic: np.array
        The predictions from `model_fit_i` on the complete test data
        
    y_pred_ii: np.array
        The predictions from `model_fit_i` on the incomplete test data

    y_test: np.array
        The true test values
    """
    model_fit_c = sklearn.clone(model)
    model_fit_c.fit(incomplete_data.X_train_complete, incomplete_data.y_train)
    
    model_fit_i = sklearn.clone(model)
    model_fit_i.fit(incomplete_data.X_train_incomplete, incomplete_data.y_train)
    
    y_pred_cc = model_fit_c.predict(incomplete_data.X_test_complete)
    y_pred_ci = model_fit_c.predict(incomplete_data.X_test_incomplete)
    y_pred_ic = model_fit_i.predict(incomplete_data.X_test_complete)
    y_pred_ii = model_fit_i.predict(incomplete_data.X_test_incomplete)
    
    ret = TrainingResults(
        model_fit_c,
        model_fit_i,
        y_pred_cc,
        y_pred_ic,
        y_pred_ci,
        y_pred_ii,
        incomplete_data.y_test
    )
    
    return ret