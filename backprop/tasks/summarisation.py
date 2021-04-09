from typing import List, Tuple, Union, Dict
from .base import Task
from backprop.models import BaseModel, AutoModel
from transformers.optimization import Adafactor
from backprop.utils.datasets import TextToTextDataset

import requests

TASK = "summarisation"

DEFAULT_LOCAL_MODEL = "t5-base-qa-summary-emotion"

LOCAL_ALIASES = {
    "english": "t5-base-qa-summary-emotion"
}

class Summarisation(Task):
    """
    Task for summarisation.

    Attributes:
        model:
            1. Model name
            2. Model name on Backprop's summarisation endpoint
            3. Model object that implements the summarisation task
        local (optional): Run locally. Defaults to False
        api_key (optional): Backprop API key for non-local inference
        device (optional): Device to run inference on. Defaults to "cuda" if available.
    """
    def __init__(self, model: Union[str, BaseModel] = None,
                local: bool = False, api_key: str = None, device: str = None):
        models = AutoModel.list_models(task=TASK)

        super().__init__(model, local=local, api_key=api_key, device=device,
                        models=models, task=TASK,
                        default_local_model=DEFAULT_LOCAL_MODEL)
    
    @staticmethod
    def list_models(return_dict=False, display=False, limit=None):
        return AutoModel.list_models(task=TASK, return_dict=return_dict, display=display, limit=limit)

    def __call__(self, text: Union[str, List[str]]):
        """Perform summarisation on input text.

        Args:
            text: string or list of strings to be summarised - keep each string below 500 words.

        Returns:
            Summary string or list of summary strings.
        """
        task_input = {
            "text": text
        }
        if self.local:
            return self.model(task_input, task="summarisation")
        else:
            task_input["model"] = self.model

            res = requests.post("https://api.backprop.co/summarisation", json=task_input,
                                headers={"x-api-key": self.api_key}).json()

            if res.get("message"):
                raise Exception(f"Failed to make API request: {res['message']}")

            return res["summary"]
    
    def step(self, batch, batch_idx):
        return self.model.training_step(batch)
        
    def configure_optimizers(self):
        return Adafactor(params=self.model.parameters(), lr=1e-3, scale_parameter=False, relative_step=False)
    
    def finetune(self, params, validation_split: Union[float, Tuple[List[int], List[int]]]=0.15,
                  max_input_length: int=512, max_output_length: int=128,
                  epochs: int=20, batch_size: int=None,
                  optimal_batch_size: int=None, early_stopping_epochs: int=1,
                  train_dataloader=None, val_dataloader=None, step=None,
                  configure_optimizers=None):
        """
        Later
        """
        inputs = params["input_text"]
        outputs = params["output_text"]
        assert len(inputs) == len(outputs)

        step = step or self.step
        configure_optimizers = configure_optimizers or self.configure_optimizers
        
        dataset_params = {
            "input": inputs,
            "output": outputs,
            "max_input_length": max_input_length,
            "max_output_length": max_output_length
        }

        print("Processing data...")
        dataset = TextToTextDataset(dataset_params, task=TASK, process_batch=self.model.process_batch, length=len(inputs))

        super().finetune(dataset=dataset, validation_split=validation_split,
                        epochs=epochs, batch_size=batch_size, optimal_batch_size=optimal_batch_size,
                        early_stopping_epochs=early_stopping_epochs,
                        train_dataloader=train_dataloader, val_dataloader=val_dataloader,
                        step=step, configure_optimizers=configure_optimizers)
        



