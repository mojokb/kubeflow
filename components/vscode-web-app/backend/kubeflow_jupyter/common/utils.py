import datetime as dt
import json
import logging
import os
import sys

import yaml
from collections import defaultdict
from flask import request
from kubernetes import client

from . import api

# The backend will send the first config it will successfully load
CONFIGS = [
    "/etc/config/spawner_ui_config.yaml",
    "./kubeflow_jupyter/common/yaml/spawner_ui_config.yaml",
]

# The values of the headers to look for the User info
USER_HEADER = os.getenv("USERID_HEADER", "X-Goog-Authenticated-User-Email")
USER_PREFIX = os.getenv("USERID_PREFIX", "accounts.google.com:")

EVENT_TYPE_NORMAL = "Normal"
EVENT_TYPE_WARNING = "Warning"

STATUS_ERROR = "error"
STATUS_WARNING = "warning"
STATUS_RUNNING = "running"
STATUS_WAITING = "waiting"


# Logging
def create_logger(name):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        )
    )
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger


logger = create_logger(__name__)


# Utils
def get_username_from_request():
    if USER_HEADER not in request.headers:
        logger.debug("User header not present!")
        username = None
    else:
        user = request.headers[USER_HEADER]
        username = user.replace(USER_PREFIX, "")
        logger.debug(
            "User: '{}' | Headers: '{}' '{}'".format(
                username, USER_HEADER, USER_PREFIX
            )
        )

    return username


def load_param_yaml(f, **kwargs):
    c = None
    try:
        with open(f, "r") as f:
            c = f.read().format(**kwargs)
    except IOError:
        logger.info("Error opening: {}".format(f))
        return None

    try:
        if yaml.safe_load(c) is None:
            # YAML exists but is empty
            return {}
        else:
            # YAML exists and is not empty
            return yaml.safe_load(c)
    except yaml.YAMLError as e:
        logger.warning("Couldn't load yaml: {}".format(e))
        return None


def spawner_ui_config():
    for config in CONFIGS:
        c = None
        try:
            with open(config, "r") as f:
                c = f.read()
        except IOError:
            logger.warning("Config file '{}' is not found".format(config))
            continue

        try:
            if yaml.safe_load(c) is None:
                # YAML exists but is empty
                return {}
            else:
                # YAML exists and is not empty
                logger.info("Sending config file '{}'".format(config))
                return yaml.safe_load(c)["spawnerFormDefaults"]
        except yaml.YAMLError:
            logger.error("Vscode config is not a valid yaml")
            return {}
        except AttributeError as e:
            logger.error(
                "Can't load the config at {}: {}".format(config, str(e))
            )

    logger.warning("Couldn't load any config")
    return {}


def get_uptime(then):
    now = dt.datetime.now()
    then = dt.datetime.strptime(then, "%Y-%m-%dT%H:%M:%SZ")
    diff = now - then.replace(tzinfo=None)

    days = diff.days
    hours = int(diff.seconds / 3600)
    mins = int((diff.seconds % 3600) / 60)

    age = ""
    if days > 0:
        if days == 1:
            age = str(days) + " day"
        else:
            age = str(days) + " days"
    else:
        if hours > 0:
            if hours == 1:
                age = str(hours) + " hour"
            else:
                age = str(hours) + " hours"
        else:
            if mins == 0:
                return "just now"
            if mins == 1:
                age = str(mins) + " min"
            else:
                age = str(mins) + " mins"

    return age + " ago"


def handle_storage_class(vol):
    # handle the StorageClass
    if "class" not in vol:
        return None
    if vol["class"] == "{empty}":
        return ""
    if vol["class"] == "{none}":
        return None
    else:
        return vol["class"]


# Volume handling functions
def volume_from_config(config_vol, vscode):
    """
    Create a Volume Dict from the config.yaml. This dict has the same fields as
    a Volume returned from the frontend
    """
    vol_name = config_vol["name"]["value"].replace(
        "{vscode-name}", vscode["name"]
    )
    vol_class = handle_storage_class(config_vol["class"]["value"])

    return {
        "name": vol_name,
        "type": config_vol["type"]["value"],
        "size": config_vol["size"]["value"],
        "mode": config_vol["accessModes"]["value"],
        "path": config_vol["mountPath"]["value"],
        "class": vol_class,
        "extraFields": config_vol.get("extra", {}),
    }


def pvc_from_dict(vol, namespace):
    if vol is None:
        return None

    return client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name=vol["name"], namespace=namespace,),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=[vol["mode"]],
            storage_class_name=handle_storage_class(vol),
            resources=client.V1ResourceRequirements(
                requests={"storage": vol["size"]}
            ),
        ),
    )


def get_workspace_vol(body, defaults):
    """
    Checks the config and the form values and returns a Volume Dict for the
    workspace. If the workspace is readOnly, then the value from the config
    will be used instead. The Volume Dict has the same format as the Volume
    interface of the frontend.
    """
    default_ws = volume_from_config(defaults["workspaceVolume"]["value"], body)
    form_ws = body.get("workspace", None)

    if defaults["workspaceVolume"].get("readOnly", False):
        ws = default_ws
        logger.info("Using the default Workspace Volume: {}".format(ws))
    elif form_ws is not None:
        ws = form_ws
        logger.info("Using form's Workspace Volume: {}".format(ws))
    else:
        ws = default_ws
        logger.info("Using the default Workspace Volume: {}".format(ws))

    return ws


def get_data_vols(body, defaults):
    """
    Checks the config and the form values and returns a list of Volume
    Dictionaries for the Vscode's Data Volumes. If the Data Volumes are
    readOnly, then the value from the config will be used instead. The Volume
    Dict has the same format as the Volume interface of the frontend.
    """
    default_vols = [
        volume_from_config(vol["value"], body)
        for vol in defaults["dataVolumes"]["value"]
    ]
    form_vols = body.get("datavols", [])

    if defaults["dataVolumes"].get("readOnly", False):
        vols = default_vols
        logger.info("Using the default Data Volumes: {}".format(vols))
    elif "datavols" in body:
        vols = form_vols
        logger.info("Using the form's Data Volumes: {}".format(vols))
    else:
        vols = default_vols
        logger.info("Using the default Data Volumes: {}".format(vols))

    return vols


# Functions for transforming the data from k8s api
def process_pvc(rsrc):
    # VAR: change this function according to the main resource
    res = {
        "name": rsrc.metadata.name,
        "namespace": rsrc.metadata.namespace,
        "size": rsrc.spec.resources.requests["storage"],
        "mode": rsrc.spec.access_modes[0],
        "class": rsrc.spec.storage_class_name,
    }
    return res


def process_resource(rsrc, rsrc_events):
    # VAR: change this function according to the main resource
    cntr = rsrc["spec"]["template"]["spec"]["containers"][0]
    status, reason = process_status(rsrc, rsrc_events)

    res = {
        "name": rsrc["metadata"]["name"],
        "namespace": rsrc["metadata"]["namespace"],
        "age": get_uptime(rsrc["metadata"]["creationTimestamp"]),
        "image": cntr["image"],
        "shortImage": cntr["image"].split("/")[-1],
        "cpu": cntr["resources"]["requests"]["cpu"],
        "memory": cntr["resources"]["requests"]["memory"],
        "volumes": [v["name"] for v in cntr["volumeMounts"]],
        "status": status,
        "reason": reason,
    }
    return res


def process_status(rsrc, rsrc_events):
    """
    Return status and reason. Status may be [running|waiting|warning|error]
    """
    # If the Vscode is being deleted, the status will be waiting
    if "deletionTimestamp" in rsrc["metadata"]:
        return STATUS_WAITING, "Deleting Vscode Server"

    # Check the status
    try:
        s = rsrc["status"]["containerState"]
    except KeyError:
        s = ""

    # Use conditions on the Jupyter vscode (i.e., s) to determine overall status
    # If no container state is available, we try to extract information about why
    # the vscode is not starting from the vscode's events (see find_error_event)
    if "running" in s:
        status, reason = STATUS_RUNNING, "Running"
    elif "terminated" in s:
        status, reason = STATUS_ERROR, "The Pod has Terminated"
    else:
        if "waiting" in s:
            reason = s["waiting"]["reason"]
            status = STATUS_ERROR if reason == "ImagePullBackOff" else STATUS_WAITING
        else:
            status, reason = STATUS_WAITING, "Scheduling the Pod"
        # Provide the user with detailed information (if any) about why the vscode is not starting
        status_event, reason_event = find_error_event(rsrc_events)
        if status_event:
            status, reason = status_event, reason_event

    return status, reason


def find_error_event(rsrc_events):
    '''
    Returns status and reason from the latest event that surfaces the cause
    of why the resource could not be created. For a Vscode, it can be due to:

          EVENT_TYPE      EVENT_REASON      DESCRIPTION   
          Warning         FailedCreate      pods "x" is forbidden: error looking up service account ... (originated in statefulset)
          Warning         FailedScheduling  0/1 nodes are available: 1 Insufficient cpu (originated in pod)

    '''
    for e in sorted(rsrc_events, key=event_timestamp, reverse=True):
        if e.type == EVENT_TYPE_WARNING:
            return STATUS_WAITING, e.message
    return None, None


def event_timestamp(event):
    return event.metadata.creation_timestamp.replace(tzinfo=None)


# Vscode YAML processing
def set_vscode_image(vscode, body, defaults):
    """
    If the image is set to readOnly, use only the value from the config
    """
    if defaults["image"].get("readOnly", False):
        image = defaults["image"]["value"]
        logger.info("Using default Image: " + image)
    elif body.get("customImageCheck", False):
        image = body["customImage"]
        logger.info("Using form's custom Image: " + image)
    elif "image" in body:
        image = body["image"]
        logger.info("Using form's Image: " + image)
    else:
        image = defaults["image"]["value"]
        logger.info("Using default Image: " + image)

    vscode["spec"]["template"]["spec"]["containers"][0]["image"] = image


def set_vscode_cpu(vscode, body, defaults):
    container = vscode["spec"]["template"]["spec"]["containers"][0]

    if defaults["cpu"].get("readOnly", False):
        cpu = defaults["cpu"]["value"]
        logger.info("Using default CPU: " + cpu)
    elif body.get("cpu", ""):
        cpu = body["cpu"]
        logger.info("Using form's CPU: " + cpu)
    else:
        cpu = defaults["cpu"]["value"]
        logger.info("Using default CPU: " + cpu)

    container["resources"]["requests"]["cpu"] = cpu


def set_vscode_memory(vscode, body, defaults):
    container = vscode["spec"]["template"]["spec"]["containers"][0]

    if defaults["memory"].get("readOnly", False):
        memory = defaults["memory"]["value"]
        logger.info("Using default Memory: " + memory)
    elif body.get("memory", ""):
        memory = body["memory"]
        logger.info("Using form's Memory: " + memory)
    else:
        memory = defaults["memory"]["value"]
        logger.info("Using default Memory: " + memory)

    container["resources"]["requests"]["memory"] = memory


def set_vscode_gpus(vscode, body, defaults):
    gpus = None
    gpuDefaults = defaults.get("gpus", {})
    if gpuDefaults.get("readOnly", False):
        # The server should not allow the user to set the GPUs
        # if the config's value is readOnly. Use the config's value
        gpus = gpuDefaults["value"]
        logger.info(f"Using default GPU config: {gpus}")

    elif "gpus" not in body:
        # Try to load the default values. If they don't exist, don't use GPUs
        if "gpus" not in defaults:
            logger.info(
                "No 'gpus' value in either the form's body or in"
                " the default config's values. Will not use any GPUs"
            )
            return
        else:
            gpus = gpuDefaults["value"]
            logger.info(f"Using default GPU config: {gpus}")

    else:
        # Make sure the GPUs value in the request is properly formatted
        gpus = body["gpus"]
        logger.info(f"Using form's GPUs: {gpus}")

        if "num" not in gpus:
            logger.error("'gpus' must have a 'num' field")
            return

        if gpus["num"] != "none" and "vendor" not in gpus:
            logger.error("'gpus' must have a 'vendor' field")
            return

        if gpus["num"] != "none":
            try:
                int(gpus["num"])
            except ValueError:
                logger.error(f"gpus.num is not a valid number: {gpus['num']}")
                return

    # Add the GPU annotation
    if gpus["num"] == "none":
        return

    container = vscode["spec"]["template"]["spec"]["containers"][0]
    vendor = gpus["vendor"]
    num = int(gpus["num"])

    limits = container["resources"].get("limits", {})
    limits[vendor] = num

    container["resources"]["limits"] = limits


def set_vscode_configurations(vscode, body, defaults):
    vscode_labels = vscode["metadata"]["labels"]

    if defaults["configurations"].get("readOnly", False):
        labels = defaults["configurations"]["value"]
        logger.info("Using default Configurations: {}".format(labels))
    elif body.get("configurations", None) is not None:
        labels = body["configurations"]
        logger.info("Using form's Configurations: {}".format(labels))
    else:
        labels = defaults["configurations"]["value"]
        logger.info("Using default Configurations: {}".format(labels))

    if not isinstance(labels, list):
        logger.warning(
            "Labels for PodDefaults are not list: {}".format(labels)
        )
        return

    for l in labels:
        vscode_labels[l] = "true"


def set_vscode_extra_resources(vscode, body, defaults):
    r = {"success": True, "log": ""}
    container = vscode["spec"]["template"]["spec"]["containers"][0]

    if defaults["extraResources"].get("readOnly", False):
        resources_str = defaults["extraResources"]["value"]
        logger.info("Using the default Extra Resources: " + resources_str)
    elif body.get("extra", ""):
        resources_str = body["extra"]
        logger.info("Using the form's Extra Resources: " + resources_str)
    else:
        resources_str = defaults["extraResources"]["value"]
        logger.info("Using the default Extra Resources: " + resources_str)

    try:
        extra = json.loads(resources_str)
    except Exception as e:
        r["success"] = False
        r["log"] = api.parse_error(e)
        return r

    container["resources"]["limits"] = extra
    return r


def set_vscode_shm(vscode, body, defaults):
    if defaults["shm"].get("readOnly", False):
        if not defaults["shm"]["value"]:
            return
    elif "shm" in body:
        if not body["shm"]:
            return
    else:
        if not defaults["shm"]["value"]:
            return

    vscode_spec = vscode["spec"]["template"]["spec"]
    vscode_cont = vscode["spec"]["template"]["spec"]["containers"][0]

    shm_volume = {"name": "dshm", "emptyDir": {"medium": "Memory"}}
    vscode_spec["volumes"].append(shm_volume)
    shm_mnt = {"mountPath": "/dev/shm", "name": "dshm"}
    vscode_cont["volumeMounts"].append(shm_mnt)


def add_vscode_volume(vscode, vol_name, claim, mnt_path):
    spec = vscode["spec"]["template"]["spec"]
    container = vscode["spec"]["template"]["spec"]["containers"][0]

    volume = {"name": vol_name, "persistentVolumeClaim": {"claimName": claim}}
    spec["volumes"].append(volume)

    # Container Mounts
    mnt = {"mountPath": mnt_path, "name": vol_name}
    container["volumeMounts"].append(mnt)


def add_vscode_volume_secret(nb, secret, secret_name, mnt_path, mode):
    # Create the volume in the Pod
    spec = nb["spec"]["template"]["spec"]
    container = nb["spec"]["template"]["spec"]["containers"][0]

    volume = {
        "name": secret,
        "secret": {"defaultMode": mode, "secretName": secret_name, },
    }
    spec["volumes"].append(volume)

    # Container volumeMounts
    mnt = {
        "mountPath": mnt_path,
        "name": secret,
    }
    container["volumeMounts"].append(mnt)
