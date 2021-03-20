import torch
from PIL import Image
from typing import Union, List
from efficientnet_pytorch import EfficientNet as EfficientNet_pt
from torchvision import transforms
from torchvision.datasets import ImageFolder
from random import shuffle
from backprop.models import PathModel, Finetunable
from backprop.utils.download import download
from pytorch_lightning.callbacks.early_stopping import EarlyStopping
from torch.utils.data import DataLoader
from functools import partial
import torch.nn.functional as F
import pytorch_lightning as pl
import json
import os

from io import BytesIO
import base64

IMAGENET_LABELS_URL = "https://raw.githubusercontent.com/backprop-ai/backprop/ic-finetuning/backprop/models/efficientnet/imagenet_labels.txt"

class EfficientNet(PathModel, Finetunable):
    def __init__(self, model_path="efficientnet-b0", init_model=None,
                init_tokenizer=None, device=None):
        Finetunable.__init__(self)
        
        self.image_size = EfficientNet_pt.get_image_size(model_path)
        self.num_classes = 1000

        if init_model is None:
            init_model = partial(EfficientNet_pt.from_pretrained, num_classes=self.num_classes)
        
        with open(download(IMAGENET_LABELS_URL, "efficientnet"), "r") as f:
            self.labels = json.load(f)

        self.tfms = transforms.Compose([
                transforms.Resize(self.image_size, interpolation=Image.BICUBIC),
                transforms.CenterCrop(self.image_size),
                lambda image: image.convert("RGB"),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])

        PathModel.__init__(self, model_path, init_model)
        
        self.name = model_path
        self.description = "EfficientNet is an image classification model that achieves state-of-the-art accuracy while being an order-of-magnitude smaller and faster than previous models. Trained on ImageNet's 1000 categories."
        self.tasks = ["image-classification"]

    def __call__(self, task_input, task="image-classification"):
        if task == "image-classification":
            image_base64 = task_input.get("image")

            return self.image_classification(image_base64=image_base64)

    @torch.no_grad()
    def image_classification(self, image_base64: Union[str, List[str]], top_k=10):
        # TODO: Proper batching
        is_list = False

        if type(image_base64) == list:
            is_list = True

        if not is_list:
            image_base64 = [image_base64]
        
        probabilities = []

        for image_base64 in image_base64:

            # Not bytes
            if type(image_base64) == str:
                image_base64 = image_base64.split(",")[-1]

            image = BytesIO(base64.b64decode(image_base64))
            image = Image.open(image)

            image = self.tfms(image).unsqueeze(0).to(self._model_device)

            logits = self.model(image)
            preds = torch.topk(logits, k=top_k).indices.squeeze(0).tolist()
            dist = torch.softmax(logits, dim=1)
            probs = {}
            for idx in preds:
                label = self.labels[str(idx)]
                prob = dist[0, idx].item()

                probs[label] = prob

            probabilities.append(probs)                

        if is_list == False:
            probabilities = probabilities[0]

        return probabilities

    def configure_optimizers(self):
        return torch.optim.SGD(params=self.model.parameters(), lr=1e-1, weight_decay=1e-4)

    def training_step(self, batch, batch_idx):
        inputs, targets = batch
        outputs = self.model(inputs)
        loss = F.cross_entropy(outputs, targets)
        self.log("train_loss", loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        return loss
    
    def validation_step(self, batch, batch_idx):
        inputs, targets = batch
        outputs = self.model(inputs)
        loss = F.cross_entropy(outputs, targets)
        self.log("val_loss", loss, prog_bar=True, on_epoch=True, logger=True)
        return loss

    def finetune(self, image_dir: str, validation_split: float = 0.15, epochs: int = 20):
        OPTIMAL_BATCH_SIZE = 128
        
        dataset = ImageFolder(image_dir, transform=self.tfms)
        self.labels = {str(v): k for k, v in dataset.class_to_idx.items()}
        num_classes = len(dataset.classes)

        if self.num_classes != num_classes:
            self.num_classes = num_classes
            self.model = EfficientNet_pt.from_pretrained(self.model_path, num_classes=num_classes)

        Finetunable.finetune(self, dataset, validation_split=validation_split,
            epochs=epochs, optimal_batch_size=OPTIMAL_BATCH_SIZE)