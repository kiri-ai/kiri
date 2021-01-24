from typing import List, Tuple, Union
from ..models import BaseModel
from ..custom_models import T5QASummaryEmotion
from .base import Task

import requests

DEFAULT_LOCAL_MODEL = "kiri-ai/t5-base-qa-summary-emotion"

LOCAL_MODELS = {
    "english": DEFAULT_LOCAL_MODEL
}

DEFAULT_API_MODEL = "english"

API_MODELS = ["english"]

class Summarisation(Task):
    def __init__(self, model: Union[str, BaseModel] = None, model_class=T5QASummaryEmotion,
                local: bool = False, api_key: str = None, device: str = "cpu",
                init: bool = False):

        super().__init__(model, local=local, api_key=api_key, device=device,
                        init=init, local_models=LOCAL_MODELS, api_models=API_MODELS,
                        default_local_model=DEFAULT_LOCAL_MODEL,
                        default_api_model=DEFAULT_API_MODEL)
        
        # Model must implement the task
        if self.local:
            # Still needs to be initialised
            if type(self.model) == str:
                self.model = model_class(self.model, init=init, device=device)

            task = getattr(self.model, "summarise", None)
            if not callable(task):
                raise ValueError(f"The model {model} cannot be used for summarisation.\
                                It does not implement the 'summarise' method.")
    
    def __call__(self, text):
        if self.local:
            return self.model.summarise(text)
        else:
            body = {
                "text": text,
                "model": self.model
            }

        res = requests.post("https://api.kiri.ai/summarisation", json=body,
                            headers={"x-api-key": self.api_key}).json()

        return res["summary"]