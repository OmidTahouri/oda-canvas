import os
import google.auth
import google.auth.transport.requests
from base_logger import logger
from apigee_utils import Apigee
import json, requests
import zipfile

from google.oauth2 import service_account

APIGEE_ORG = "smart-altar"
APIGEE_ENV = "test1"

apigee = Apigee(
    apigee_type = "x",
    org = APIGEE_ORG
)

print(apigee.list_environments())

# logger.info("Deploying proxy bundle")

API_NAME = "example-v0"

bundle_path = os.path.dirname(os.path.abspath(__file__))

logger.info("Creating proxy bundle")

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, _, files in os.walk(path):
        for file in files:
            ziph.write(
                os.path.join(root, file),
                os.path.relpath(
                    os.path.join(root, file), os.path.join(path, "..")  # noqa
                ),
            )

def create_proxy_bundle(proxy_bundle_directory, api_name, target_dir):  # noqa
    with zipfile.ZipFile(
        f"{proxy_bundle_directory}/{api_name}.zip", "w", zipfile.ZIP_DEFLATED
    ) as zipf:  # noqa
        zipdir(target_dir, zipf)

create_proxy_bundle(f"{bundle_path}", API_NAME, "apiproxy")

if not apigee.deploy_api_bundle(
    APIGEE_ENV,
    API_NAME,
    f"{bundle_path}/{API_NAME}.zip",
    False
):
    logger.error(f"Deployment failed for proxy: {API_NAME}")
