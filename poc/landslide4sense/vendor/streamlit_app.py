import os
import sys

import streamlit as st

# Add the parent directory to sys.path to allow imports from 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import io
import os

import h5py
import matplotlib.pyplot as plt
import numpy as np
import torch
import yaml

from src.deeplabv3plus_model import LandslideModel as DeepLabV3PlusModel
from src.densenet121_model import LandslideModel as DenseNet121Model
from src.efficientnetb0_model import LandslideModel as EfficientNetB0Model
from src.inceptionresnetv2_model import LandslideModel as InceptionResNetV2Model
from src.inceptionv4_model import LandslideModel as InceptionV4Model
from src.mitb1_model import LandslideModel as MiTB1Model

# Import models
from src.mobilenetv2_model import LandslideModel as MobileNetV2Model
from src.model_downloader import ModelDownloader
from src.resnet34_model import LandslideModel as ResNet34Model
from src.resnext50_32x4d_model import LandslideModel as ResNeXt50Model
from src.se_resnet50_model import LandslideModel as SEResNet50Model
from src.se_resnext50_32x4d_model import LandslideModel as SEResNeXt50Model
from src.segformer_model import LandslideModel as SegFormerB2Model
from src.vgg16_model import LandslideModel as VGG16Model

# Define available models
AVAILABLE_MODELS = {
    "mobilenetv2": {"name": "MobileNetV2", "type": "mobilenet_v2"},
    "vgg16": {"name": "VGG16", "type": "vgg16"},
    "resnet34": {"name": "ResNet34", "type": "resnet34"},
    "efficientnetb0": {"name": "EfficientNetB0", "type": "efficientnet_b0"},
    "mitb1": {"name": "MiTB1", "type": "mitb1"},
    "inceptionv4": {"name": "InceptionV4", "type": "inception_v4"},
    "densenet121": {"name": "DenseNet121", "type": "densenet121"},
    "deeplabv3plus": {"name": "DeepLabV3Plus", "type": "deeplabv3plus"},
    "resnext50": {
        "name": "ResNeXt50",
        "type": "resnext50_32x4d",
        "downloader_key": "resnext50_32x4d",
    },
    "seresnet50": {"name": "SEResNet50", "type": "se_resnet50", "downloader_key": "se_resnet50"},
    "seresnext50": {
        "name": "SEResNeXt50",
        "type": "se_resnext50_32x4d",
        "downloader_key": "se_resnext50_32x4d",
    },
    "segformerb2": {"name": "SegFormerB2", "type": "segformer_b2", "downloader_key": "segformer"},
    "inceptionresnetv2": {"name": "InceptionResNetV2", "type": "inception_resnet_v2"},
}

# Model descriptions with their respective types and descriptions
MODEL_DESCRIPTIONS = {
    model_key: {
        "type": model_info["type"],
        "description": f"{model_info['name']} - A model for landslide detection and segmentation.",
        "name": model_info["name"],
        "downloader_key": model_info.get("downloader_key", model_key),
    }
    for model_key, model_info in AVAILABLE_MODELS.items()
}

# Load the configuration file
config_str = """
model_config:
  model_type: "mobilenet_v2"
  in_channels: 14
  num_classes: 1
  encoder_weights: "imagenet"
  wce_weight: 0.5

dataset_config:
  num_classes: 1
  num_channels: 14
  channels: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
  normalize: False

train_config:
  dataset_path: ""
  checkpoint_path: "checkpoints"
  seed: 42
  train_val_split: 0.8
  batch_size: 16
  num_epochs: 100
  lr: 0.001
  device: "cuda:0"
  save_config: True
  experiment_name: "mobilenet_v2"

logging_config:
  wandb_project: "l4s"
  wandb_entity: "Silvamillion"
"""

config = yaml.safe_load(config_str)


def process_and_visualize(model_key, model_info, image_tensor, original_image, uploaded_file_name):
    """
    Process the image with the selected model and visualize results.
    """
    try:
        st.write(f"Using model: {model_info['name']}")

        # Update config for the specific model
        current_config = config.copy()
        current_config["model_config"]["model_type"] = model_info["type"]

        # Get the model class
        model_class_name = AVAILABLE_MODELS[model_key]["name"].replace("-", "") + "Model"
        if model_class_name not in globals():
            # Fallback for naming inconsistencies if any
            # Try to find it in globals
            pass
        model_class = globals()[model_class_name]

        # Initialize model downloader
        downloader = ModelDownloader()

        # Download/get model path
        download_key = model_info.get("downloader_key", model_key)
        model_path = downloader.download_model(download_key)
        st.info(f"Using model from: {model_path}")

        # Load the model
        model = model_class(current_config)
        model.load_state_dict(
            torch.load(model_path, map_location=torch.device("cpu")), strict=False
        )
        model.eval()

        # Make prediction
        with torch.no_grad():
            prediction = model(image_tensor)
            prediction = torch.sigmoid(prediction).cpu().numpy()

        # Display prediction
        st.header(f"Prediction Results - {model_info['name']}")
        fig, ax = plt.subplots(1, 3, figsize=(15, 5))

        # Normalize image for display
        img_display = original_image.transpose(1, 2, 0)  # (C, H, W) -> (H, W, C)
        img_display = (img_display - img_display.min()) / (img_display.max() - img_display.min())

        ax[0].imshow(img_display[:, :, :3])  # Display first three channels as RGB
        ax[0].set_title("Input Image")
        ax[0].axis("off")

        ax[1].imshow(prediction.squeeze(), cmap="plasma")  # Raw prediction map
        ax[1].set_title("Prediction Probability")
        ax[1].axis("off")

        ax[2].imshow(img_display[:, :, :3])
        ax[2].imshow(prediction.squeeze() > 0.5, cmap="plasma", alpha=0.4)  # Overlay
        ax[2].set_title("Overlay (Threshold > 0.5)")
        ax[2].axis("off")

        st.pyplot(fig)
        plt.close(fig)

        # Download button
        st.write(f"Download the prediction as a .npy file for {model_info['name']}:")
        npy_data = prediction.squeeze()
        st.download_button(
            label=f"Download Prediction - {model_info['name']}",
            data=npy_data.tobytes(),
            file_name=f"{uploaded_file_name.split('.')[0]}_{model_key}_prediction.npy",
            mime="application/octet-stream",
        )

    except Exception as e:
        st.error(f"Error with model {model_info['name']}: {str(e)}")
        import traceback

        st.error(traceback.format_exc())


# Streamlit app
st.set_page_config(page_title="Landslide Detection", layout="wide")

st.title("Landslide Detection")
st.markdown(
    """
## Instructions
1. Select a model from the sidebar or choose to run all models.
2. Upload one or more `.h5` files.
3. The app will process the files and display the input image, prediction, and overlay.
4. You can download the prediction results.
"""
)

# Sidebar for model selection
st.sidebar.title("Model Selection")
model_option = st.sidebar.radio("Choose an option", ["Select a single model", "Run all models"])

selected_model_key = None
if model_option == "Select a single model":
    selected_model_key = st.sidebar.selectbox("Select Model", list(MODEL_DESCRIPTIONS.keys()))
    selected_model_info = MODEL_DESCRIPTIONS[selected_model_key]

    # Display model details in the sidebar
    st.sidebar.markdown("### Model Details")
    st.sidebar.markdown(f"**Model Name:** {selected_model_info['name']}")
    st.sidebar.markdown(f"**Model Type:** {selected_model_info['type']}")
    st.sidebar.markdown(f"**Description:** {selected_model_info['description']}")

# Main content
st.header("Upload Data")

# Initialize session state for error tracking if not exists
if "upload_errors" not in st.session_state:
    st.session_state.upload_errors = []

uploaded_files = st.file_uploader(
    "Choose .h5 files...",
    type="h5",
    accept_multiple_files=True,
    help="Upload your .h5 files here. Maximum file size is 200MB.",
)

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.write(f"Processing file: {uploaded_file.name}")
        st.write(f"File size: {uploaded_file.size} bytes")

        with st.spinner("Classifying..."):
            try:
                # Read the file directly using BytesIO
                bytes_data = uploaded_file.getvalue()
                bytes_io = io.BytesIO(bytes_data)

                with h5py.File(bytes_io, "r") as hdf:
                    if "img" not in hdf:
                        st.error(f"Error: 'img' dataset not found in {uploaded_file.name}")
                        continue

                    data = np.array(hdf.get("img"))
                    data[np.isnan(data)] = 0.000001
                    channels = config["dataset_config"]["channels"]

                    # Prepare image
                    # Assuming data shape is (14, 128, 128) based on typical satellite data or (128, 128, 14)
                    # The original code did: image[:, :, i] = data[band-1] implying data is (14, 128, 128) if accessed by index
                    # But later it did data[:, :, channel-1] in the else block?
                    # Let's check the original code logic again.
                    # Original code had two different logic blocks for data loading!
                    # Block 1 (single model): image[:, :, i] = data[band-1] -> implies data is (C, H, W)
                    # Block 2 (all models): image[:, :, i] = data[:, :, channel-1] -> implies data is (H, W, C)

                    # I will assume (C, H, W) is more standard for HDF5 'img' usually, but let's try to be robust or pick one.
                    # Given the inconsistency, I'll check data shape.

                    image = np.zeros((128, 128, len(channels)))

                    if data.ndim == 3:
                        if data.shape[0] == 14:  # (C, H, W)
                            for i, band in enumerate(channels):
                                image[:, :, i] = data[band - 1, :, :]
                        elif data.shape[2] == 14:  # (H, W, C)
                            for i, band in enumerate(channels):
                                image[:, :, i] = data[:, :, band - 1]
                        else:
                            st.warning(f"Unexpected data shape: {data.shape}. Assuming (C, H, W).")
                            for i, band in enumerate(channels):
                                if band - 1 < data.shape[0]:
                                    image[:, :, i] = data[band - 1, :, :]
                    else:
                        st.error(f"Data has {data.ndim} dimensions, expected 3.")
                        continue

                    # Prepare for model (Batch, Channel, Height, Width)
                    # image is currently (H, W, C)
                    image_display = image.transpose(2, 0, 1)  # (C, H, W)
                    image_tensor = (
                        torch.from_numpy(image_display).unsqueeze(0).float()
                    )  # (1, C, H, W)

                    if model_option == "Select a single model":
                        process_and_visualize(
                            selected_model_key,
                            selected_model_info,
                            image_tensor,
                            image_display,
                            uploaded_file.name,
                        )
                    else:
                        for model_key, model_info in MODEL_DESCRIPTIONS.items():
                            process_and_visualize(
                                model_key,
                                model_info,
                                image_tensor,
                                image_display,
                                uploaded_file.name,
                            )

            except Exception as e:
                st.error(f"Error processing file {uploaded_file.name}: {str(e)}")
                import traceback

                st.error(traceback.format_exc())
                continue

st.success("Done!")
