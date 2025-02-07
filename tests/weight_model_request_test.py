#########################
# weight_mode_request.py
#
# This file covers the following cases.
# - getting weight from model server based on available features
#
#########################

import os
import json
import time
import sys

import requests

from kepler_model.util.train_types import FeatureGroups, FeatureGroup, ModelOutputType
from kepler_model.util.loader import get_download_output_path
from kepler_model.estimate.model_server_connector import list_all_models
from kepler_model.util.config import get_model_server_req_endpoint, download_path

from tests.extractor_test import test_energy_source
from tests.estimator_power_request_test import generate_request

os.environ["MODEL_SERVER_URL"] = "http://localhost:8100"

weight_available_trainers = ["SGDRegressorTrainer"]

if __name__ == "__main__":
    # test getting model from server
    os.environ["MODEL_SERVER_ENABLE"] = "true"
    energy_source = test_energy_source

    available_models = list_all_models()
    while len(available_models) == 0:
        time.sleep(1)
        print("wait for kepler model server response")
        available_models = list_all_models()

    for output_type_name, valid_fgs in available_models.items():
        output_type = ModelOutputType[output_type_name]
        output_path = get_download_output_path(download_path, energy_source, output_type)
        for fg_name, best_model in valid_fgs.items():
            for trainer in weight_available_trainers:
                print("feature group: ", fg_name)
                metrics = FeatureGroups[FeatureGroup[fg_name]]
                request_json = generate_request(trainer, n=10, metrics=metrics, output_type=output_type_name)
                request_json["metrics"] += request_json["system_features"]
                request_json["weight"] = "true"
                del request_json["system_features"]
                del request_json["values"]
                del request_json["system_values"]
                try:
                    response = requests.post(get_model_server_req_endpoint(), json=request_json)
                except Exception as err:
                    print("cannot get response from model server: {}".format(err))
                    sys.exit(1)
                assert response.status_code == 200, "response {} not OK".format(request_json)
                loaded_weight = json.loads(response.content)
                print(loaded_weight)
