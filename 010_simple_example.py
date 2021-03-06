"""
A script for running the models and pickers to pick P phases on coal mining
induced seismicity.

See Johnson et al. 2020 for more details.
"""
from pathlib import Path

import numpy as np

from coalpick import cnn, baer
from coalpick.core import (
    load_data,
    shuffle_data,
    train_test_split,
)
from coalpick.plot import plot_residuals, plot_waveforms, plot_training

# --------------------------- CONTROL PARAMETERS --------------------------- #
# input parameters
data_file = Path("data.parquet")  # Path to data file
dataset = "A"  # The dataset to select, if None use all
train_fraction = 0.75  # fraction of traces to use for training
training_data_repeat = 5  # Number of times to repeat training data
# Define number of passes through training data. If None, allow up to 50
# but stop after no improvements to validation are observed for 5 epochs
training_epochs = None

# cnn parameters
model_structure_path = Path("models/p_json_model.json")
model_weights_path = Path("models/p_scsn_weights.hdf5")

# output parameters
output_weights_path = Path("models/trained_cnn_weights.hdf5")
plot_path = Path("plots")  # If None dont plot
output_params_path = Path("models/optimized_baer_params.json")

# -------------------------------- PREPROCESSING ------------------------- #
# Load input data from parquet file
df = load_data(data_file, dataset)

# Split input dataframe into training and testing
random_state = np.random.RandomState(seed=42)  # Use reproducible random states
train_df, test_df = train_test_split(
    df, train_fraction=train_fraction, random_state=random_state
)

# Get sampling rate for this dataset
sr = df[("stats", "sampling_rate")].iloc[0]

# Get arrays with analyst pick shuffled +/- 50 samples and analyst pick
X_train, y_train = shuffle_data(train_df, repeat=training_data_repeat)
X_test, y_test = shuffle_data(test_df)

# ---------------------------------- CNN ----------------------------------- #
# Load the keras models and weights
model = cnn.load_model(model_structure_path, model_weights_path)

# Make predictions before (re)training the model
cnn_pre_train = cnn.predict(model, X_test)

# Train model
history = cnn.fit(
    model,
    X_train,
    y_train,
    epochs=training_epochs,
    validation_data=(X_test, y_test),
)

# Save weights (uncomment next line to save the weights from training)
# model.save_weights(output_weights_path)

# Make predictions after (re)training the model
cnn_post_train = cnn.predict(model, X_test)

# ---------------------------------- BAER ---------------------------------- #
# Creating new optimized parameters for the baer picker
op_baer_params = baer.fit(X_train, y_train, sr)

# Save baer parameters (uncomment next line to save the parameters from optimization)
# baer.save_params(op_baer_params, output_params_path)

# Make predictions with the optimized parameters
baer_post_train = baer.predict(op_baer_params, X_test, sr)

# ---------------------------------- PLOTTING ------------------------------ #
if plot_path is not None:

    # Plot training losses
    plot_training(history.history, plot_path / "training.png")

    # Plot residual histograms
    predictions = {
        "Base CNN": cnn_pre_train,
        "Trained Baer": baer_post_train,
        "Trained CNN": cnn_post_train,
    }
    plot_residuals(
        predictions,
        y_test,
        sr=sr,
        output_path=plot_path / "residual_histograms.png",
    )

    # Plot the first 5 waveforms and their picks.
    for i in range(5):
        picks = {
            "manual": y_test[i],
            "SCSN CNN": cnn_pre_train[i],
            "optimized BAER picker": baer_post_train[i],
            "retrained CNN": cnn_post_train[i],
        }
        path = plot_path / f"example_waveforms_{i}.png"
        plot_waveforms(X_test[i], picks, path)
