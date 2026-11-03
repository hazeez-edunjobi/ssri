import json
import os
from pathlib import Path

import requests
import streamlit as st
from tqdm.auto import tqdm


class ModelDownloader:
    def __init__(self):
        # Create models directory for caching
        self.models_dir = Path("models").resolve()
        self.models_dir.mkdir(exist_ok=True)

        # HuggingFace model repository details
        self.hf_model_url = "https://huggingface.co/harshinde/DeepSlide_Models/resolve/main/"

        # Model mapping with file names
        self.model_files = {
            "deeplabv3plus": {"file": "deeplabv3.pth", "url": f"{self.hf_model_url}deeplabv3.pth"},
            "densenet121": {
                "file": "densenet121.pth",
                "url": f"{self.hf_model_url}densenet121.pth",
            },
            "efficientnetb0": {
                "file": "efficientnetb0.pth",
                "url": f"{self.hf_model_url}effucientnetb0.pth",
            },
            "inceptionresnetv2": {
                "file": "inceptionresnetv2.pth",
                "url": f"{self.hf_model_url}inceptionresnetv2.pth",
            },
            "inceptionv4": {
                "file": "inceptionv4.pth",
                "url": f"{self.hf_model_url}inceptionv4.pth",
            },
            "mitb1": {"file": "mitb1.pth", "url": f"{self.hf_model_url}mitb1.pth"},
            "mobilenetv2": {
                "file": "mobilenetv2.pth",
                "url": f"{self.hf_model_url}mobilenetv2.pth",
            },
            "resnet34": {"file": "resnet34.pth", "url": f"{self.hf_model_url}resnet34.pth"},
            "resnext50_32x4d": {
                "file": "resnext50-32x4d.pth",
                "url": f"{self.hf_model_url}resnext50-32x4d.pth",
            },
            "se_resnet50": {
                "file": "se_resnet50.pth",
                "url": f"{self.hf_model_url}se_resnet50.pth",
            },
            "se_resnext50_32x4d": {
                "file": "se_resnext50_32x4d.pth",
                "url": f"{self.hf_model_url}se_resnext50_32x4d.pth",
            },
            "segformer": {"file": "segformer.pth", "url": f"{self.hf_model_url}segformer.pth"},
            "vgg16": {"file": "vgg16.pth", "url": f"{self.hf_model_url}vgg16.pth"},
        }

    def download_model(self, model_name):
        """
        Download model from Hugging Face Models repository
        Args:
            model_name (str): Name of the model to download
        Returns:
            str: Path to the downloaded model file
        """
        if model_name not in self.model_files:
            raise ValueError(
                f"Model {model_name} not found. Available models: {list(self.model_files.keys())}"
            )

        model_info = self.model_files[model_name]
        model_path = self.models_dir / model_info["file"]

        if not model_path.exists():
            print(f"Downloading {model_name} model...")
            # Use 'url' if available, otherwise fallback or error (logic simplified for now as per plan)
            if "url" in model_info:
                url = model_info["url"]
            else:
                # Fallback for models without explicit URL in the map (though all seem to have it or use ID)
                # Assuming the pattern from init for others
                url = f"{self.hf_model_url}{model_info['file']}"

            response = requests.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            with (
                open(model_path, "wb") as f,
                tqdm(
                    total=total_size,
                    unit="iB",
                    unit_scale=True,
                    unit_divisor=1024,
                ) as pbar,
            ):
                for data in response.iter_content(chunk_size=1024):
                    size = f.write(data)
                    pbar.update(size)
            print(f"Model downloaded successfully to {model_path}")

        return str(model_path)

    def list_available_models(self):
        """
        List all available models
        Returns:
            list: List of available model names
        """
        return list(self.model_files.keys())
