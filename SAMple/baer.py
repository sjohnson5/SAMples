"""
Baer picker functions of SAMple.
"""

from pathlib import Path
from json import dump

import numpy as np
from obspy.signal.trigger import pk_baer
from scipy.optimize import differential_evolution

from SAMple.prep_utils import normalize

DEFAULT_BOUNDS = dict(tdownmax=(0, 50),
                      tupevent=(0, 10),
                      thr1=(0, 15),
                      thr2=(5, 20),
                      preset_len=(0, 200),
                      p_dur=(0, 200),
                      offset_constant=(-10, 10))


def fit(data, target, sr):
    """
    Optimizes baer picker parameters for the given data

    Parameters
    ----------
    data
        The input X data.
    target
        The target values the model should learn to predict.
    sr
        The sampling rate of the data.
    """
    result = differential_evolution(_fit, bounds=DEFAULT_BOUNDS, args=(data, target, sr))
    return result.x


def predict(params: dict, data: np.ndarray) -> np.ndarray:
    """
    Use the params to make predictions.

    Parameters
    ----------
    params
        A dictionary of the parameters required for the baer picker
    data
        The input data in the form of a numpy ndarray.
    """
    X = normalize(data)
    out = np.apply_along_axis(_pick, 1, X, params=params)
    return out


def load_params(params_path: Path) -> dict:
    """
    Load a keras model and, optionally, its weights.

    Parameters
    ----------
    params_path
        A path to a json file defining the input parameters of the baer picker.
    """
    structure_path = Path(params_path)
    assert structure_path.suffix == ".json", "structure_file must be a '.json' file"
    with structure_path.open("rb") as fi:
        params = fi.read()
    return params


def save_params(params: dict, save_path: Path)
    """
    Saves the parameters as a json file

    Parameters
    ----------
    params
        A dictionary of the parameters required for the baer picker to be saved
    save_path
        path to save the parameters to
    """
    assert save_path.suffix == ".json", "structure_file must be a '.json' file"
    save_path = Path(save_path)
    with open(save_path, 'w') as file:
        dump(params, file)


def loss_fn(pred, target, sr, uncert=30):
    """ loss function for optimizing picks, following method in 'Maurizio 2012' """
    uncert = uncert / sr

    both_inds = np.nonzero(~np.isnan(pred) & ~np.isnan(target))[0]  # both picked
    man_inds = np.nonzero(np.isnan(pred) & ~np.isnan(target))[0]  # man picked
    baer_inds = np.nonzero(~np.isnan(pred) & np.isnan(target))[0]  # baer picked
    neither_inds = np.nonzero(np.isnan(pred) & np.isnan(target))[0] # neither picked

    top = ((pred[both_inds] - target[both_inds] / sr)) ** 2
    bottom = 2 * (uncert ** 2)
    both_loss = sum(np.exp(-(top / bottom)))
    man_loss = 0 * len(man_inds)
    model_loss = (1 / 5) ** 2 * len(baer_inds)
    neither_loss = (1 / 4) * len(neither_inds)

    top = both_loss + man_loss + model_loss + neither_loss
    bottom = 0.25 * (len(baer_inds) + len(neither_inds)) + (len(both_inds) + len(man_inds))
    if bottom == 0:  # prevents divide by 0 error
        return 100
    fitness = top / bottom

    loss = 1 / fitness
    return loss


def _pick(x, params):
    """ picks a single trace with the baer picker """
    # formatting params
    tdownmax, tupevent, thr1, thr2, preset_len, p_dur, offset_constant = params
    p_ind, _ = pk_baer(x, tdownmax=tdownmax, tupevent=tupevent, thr1=thr1,
                       thr2=thr2, preset_len=preset_len, p_dur=p_dur)
    return p_ind + offset_constant


def _fit(params, data, target, sr):
    """ optimizable function to fit """
    pred = predict(params, data)
    return loss_fn(pred, target, sr)
