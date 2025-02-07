#########################
# estimator_model_request_test.py
#
# This file covers the following cases.
# - kepler-model-server is connected
#   - list all available models with its corresponding available feature groups and make a dummy PowerRequest
# - kepler-model-server is not connected, but some achived models can be download via URL.
#   - set sample model and make a dummy valid PowerRequest and another invalid PowerRequest
#
#########################
# import external modules
import shutil
import requests

# import from src
import os
import json

from kepler_model.util.train_types import FeatureGroups, FeatureGroup, ModelOutputType
from kepler_model.util.loader import get_download_output_path, default_train_output_pipeline, get_url
from kepler_model.util.config import get_init_model_url, set_env_from_model_config, download_path
from kepler_model.estimate.estimator import handle_request, loaded_model, PowerRequest
from kepler_model.estimate.model_server_connector import list_all_models
from kepler_model.estimate.archived_model import get_achived_model, reset_failed_list
from tests.extractor_test import test_energy_source

from tests.estimator_power_request_test import generate_request
from tests.http_server import http_file_server

file_server_port = 8110
# set environment
os.environ["MODEL_SERVER_URL"] = "http://localhost:8100"
model_topurl = "http://localhost:{}".format(file_server_port)
os.environ["MODEL_TOPURL"] = model_topurl
os.environ["INITIAL_PIPELINE_URL"] = os.path.join(model_topurl, "std_v0.7.11")


def test_model_request():
    http_file_server(file_server_port)
    energy_source = test_energy_source
    # test getting model from server
    os.environ["MODEL_SERVER_ENABLE"] = "true"
    available_models = list_all_models()
    assert len(available_models) > 0, "must have more than one available models"
    print("Available Models:", available_models)
    for output_type_name, valid_fgs in available_models.items():
        output_type = ModelOutputType[output_type_name]
        output_path = get_download_output_path(download_path, energy_source, output_type)
        for fg_name, best_model in valid_fgs.items():
            if os.path.exists(output_path):
                shutil.rmtree(output_path)
            if output_type.name in loaded_model and energy_source in loaded_model[output_type.name]:
                del loaded_model[output_type.name][energy_source]
            metrics = FeatureGroups[FeatureGroup[fg_name]]
            request_json = generate_request(train_name=None, n=10, metrics=metrics, output_type=output_type_name)
            data = json.dumps(request_json)
            output = handle_request(data)
            print("result {}/{} from model server: {}".format(output_type_name, fg_name, output))
            assert len(output["powers"]) > 0, "cannot get power {}\n {}".format(output["msg"], request_json)

    # test with initial models
    os.environ["MODEL_SERVER_ENABLE"] = "false"
    for output_type in ModelOutputType:
        output_type_name = output_type.name
        url = get_init_model_url(energy_source, output_type.name)
        if url != "":
            print("Download: ", url)
            response = requests.get(url)
            assert response.status_code == 200, "init url must be set and valid"
            output_path = get_download_output_path(download_path, energy_source, output_type)
            if output_type_name in loaded_model and energy_source in loaded_model[output_type.name]:
                del loaded_model[output_type_name][energy_source]
            if os.path.exists(output_path):
                shutil.rmtree(output_path)
            request_json = generate_request(None, n=10, metrics=FeatureGroups[FeatureGroup.Full], output_type=output_type_name)
            data = json.dumps(request_json)
            output = handle_request(data)
            assert len(output["powers"]) > 0, "cannot get power {}\n {}".format(output["msg"], request_json)
            print("result from {}: {}".format(url, output))

    output_type_name = "AbsPower"
    estimator_enable_key = "NODE_COMPONENTS_ESTIMATOR"
    init_url_key = "NODE_COMPONENTS_INIT_URL"
    # enable model to use
    os.environ[estimator_enable_key] = "true"

    # test getting model from archived
    os.environ["MODEL_SERVER_ENABLE"] = "false"
    output_type = ModelOutputType[output_type_name]
    output_path = get_download_output_path(download_path, energy_source, output_type)
    if output_type_name in loaded_model and energy_source in loaded_model[output_type.name]:
        del loaded_model[output_type_name][energy_source]
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    # valid model
    os.environ[init_url_key] = get_url(energy_source=energy_source, output_type=output_type, feature_group=FeatureGroup.BPFOnly, model_topurl=model_topurl, pipeline_name=default_train_output_pipeline)
    print("Requesting from ", os.environ[init_url_key])
    request_json = generate_request(None, n=10, metrics=FeatureGroups[FeatureGroup.BPFOnly], output_type=output_type_name)
    data = json.dumps(request_json)
    output = handle_request(data)
    assert len(output["powers"]) > 0, "cannot get power {}\n {}".format(output["msg"], request_json)
    print("result {}/{} from static set: {}".format(output_type_name, FeatureGroup.BPFOnly.name, output))
    del loaded_model[output_type_name][energy_source]
    # invalid model
    os.environ[init_url_key] = get_url(energy_source=energy_source, output_type=output_type, feature_group=FeatureGroup.BPFOnly, model_topurl=model_topurl, pipeline_name=default_train_output_pipeline)
    print("Requesting from ", os.environ[init_url_key])
    request_json = generate_request(None, n=10, metrics=FeatureGroups[FeatureGroup.CounterOnly], output_type=output_type_name)
    data = json.dumps(request_json)
    power_request = json.loads(data, object_hook=lambda d: PowerRequest(**d))
    output_path = get_achived_model(power_request)
    assert output_path is None, "model should be invalid\n {}".format(output_path)
    os.environ["MODEL_CONFIG"] = "{}=true\n{}={}\n".format(estimator_enable_key, init_url_key, get_url(energy_source=energy_source, output_type=output_type, feature_group=FeatureGroup.BPFOnly, model_topurl=model_topurl, pipeline_name=default_train_output_pipeline))
    set_env_from_model_config()
    print("Requesting from ", os.environ[init_url_key])
    reset_failed_list()
    if output_type_name in loaded_model and energy_source in loaded_model[output_type.name]:
        del loaded_model[output_type_name][energy_source]
    output_path = get_download_output_path(download_path, energy_source, output_type)
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    request_json = generate_request(None, n=10, metrics=FeatureGroups[FeatureGroup.BPFOnly], output_type=output_type_name)
    data = json.dumps(request_json)
    output = handle_request(data)
    assert len(output["powers"]) > 0, "cannot get power {}\n {}".format(output["msg"], request_json)


if __name__ == "__main__":
    test_model_request()
