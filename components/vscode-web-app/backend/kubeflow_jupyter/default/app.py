from flask import Flask, request, jsonify, send_from_directory
from ..common.base_app import app as base
from ..common import utils, api

app = Flask(__name__)
app.register_blueprint(base)
logger = utils.create_logger(__name__)

VSCODE = "./kubeflow_jupyter/common/yaml/vscode.yaml"


# POSTers
@app.route("/api/namespaces/<namespace>/vscodes", methods=["POST"])
def post_vscode(namespace):
    body = request.get_json()
    defaults = utils.spawner_ui_config()
    logger.info("Got Vscode: {}".format(body))

    vscode = utils.load_param_yaml(VSCODE,
                                     name=body["name"],
                                     namespace=namespace,
                                     serviceAccount="default-editor")

    utils.set_vscode_image(vscode, body, defaults)
    utils.set_vscode_cpu(vscode, body, defaults)
    utils.set_vscode_memory(vscode, body, defaults)
    utils.set_vscode_gpus(vscode, body, defaults)
    utils.set_vscode_configurations(vscode, body, defaults)

    # Workspace Volume
    workspace_vol = utils.get_workspace_vol(body, defaults)
    if not body.get("noWorkspace", False) and workspace_vol["type"] == "New":
        # Create the PVC
        ws_pvc = utils.pvc_from_dict(workspace_vol, namespace)

        logger.info("Creating Workspace Volume: {}".format(ws_pvc.to_dict()))
        r = api.create_pvc(ws_pvc, namespace=namespace)
        if not r["success"]:
            return jsonify(r)

    if not body.get("noWorkspace", False) and workspace_vol["type"] != "None":
        utils.add_vscode_volume(
            vscode,
            workspace_vol["name"],
            workspace_vol["name"],
            "/home/jovyan",
        )

    # Add the Data Volumes
    for vol in utils.get_data_vols(body, defaults):
        if vol["type"] == "New":
            # Create the PVC
            dtvol_pvc = utils.pvc_from_dict(vol, namespace)

            logger.info("Creating Data Volume {}:".format(dtvol_pvc))
            r = api.create_pvc(dtvol_pvc, namespace=namespace)
            if not r["success"]:
                return jsonify(r)

        utils.add_vscode_volume(
            vscode,
            vol["name"],
            vol["name"],
            vol["path"]
        )

    # shm
    utils.set_vscode_shm(vscode, body, defaults)

    logger.info("Creating Vscode: {}".format(vscode))
    return jsonify(api.create_vscode(vscode, namespace=namespace))


# Since Angular is a SPA, we serve index.html every time
@app.route("/")
def serve_root():
    return send_from_directory("./static/", "index.html")


@app.route("/<path:path>", methods=["GET"])
def static_proxy(path):
    logger.info("Sending file '/static/{}' for path: {}".format(path, path))
    return send_from_directory("./static/", path)


@app.errorhandler(404)
def page_not_found(e):
    logger.info("Sending file 'index.html'")
    return send_from_directory("./static/", "index.html")
