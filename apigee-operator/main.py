import kopf
import os
import google.auth
import google.auth.transport.requests
from base_logger import logger
from apigee_utils import Apigee
import json, requests
import zipfile
from jinja2 import Environment, BaseLoader
from google.oauth2 import service_account

# TODO: abstract these top-level variables
APIGEE_ORG = "caramel-medley"
APIGEE_ENV = "test-env"

BUNDLE_PATH = os.path.dirname(os.path.abspath(__file__))

# TODO: pass in the service account path/secret here (currently hard-coded on apigee_utils.py:67)
apigee = Apigee(
    apigee_type = "x",
    org = APIGEE_ORG
)

@kopf.on.create('oda.tmforum.org', 'v1beta3', 'exposedapis')
def create_exposedapi_handler(body, spec, **kwargs):
    logger.info("ExposedAPI created")

    # pseudo logic:
        # get all features/policies/capabilities from the CR
        # for each feature (with enabled = true), fetch policy template from ./apiproxy/policies/
        #     edit the policy with values from CR
        #     save the policy to ./generated/{uid}/apiproxy/policies
        # create ./generated/{uid}/apiproxy/{API_NAME}.xml
        # zip the ./generated/{uid}/apiproxy directory and save at ./generated/{uid}/{API_NAME}.zip
        # deploy the api
        # update STATUS of CR to something like "deployed"
        # get hostname from environment group, using Apigee API
        # update CR with URL of deployed proxy
        # delete the ./generated/{uid} directory

        # delete {BUNDLE_PATH}/generated/{STAGING_DIR} after deployment

    UNIQUE_ID = body['metadata']['uid']
    RESOURCE_VERSION = body['metadata']['resourceVersion']
    STAGING_DIR = f"{UNIQUE_ID}-{RESOURCE_VERSION}"

    os.makedirs(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/policies")
    os.makedirs(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/proxies")
    os.makedirs(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/targets")

    # extract core properties from CR
    API_NAME = body['metadata']['name']
    API_BASE_PATH = body['spec']['path']
    API_TARGET_URL = body['spec']['implementation']

    # TODO: abstract this to separate util file
    SPIKEARREST_REQUIRED = body['spec']['rateLimit']['enabled']

    if SPIKEARREST_REQUIRED == True:
        logger.info(f"Creating SpikeArrest policy for {API_NAME} ({STAGING_DIR})...")

        SPIKEARREST_IDENTIFIER = body['spec']['rateLimit']['identifier']
        SPIKEARREST_LIMIT = body['spec']['rateLimit']['limit']
        SPIKEARREST_INTERVAL = body['spec']['rateLimit']['interval']
        SPIKEARREST_RATE = f"{SPIKEARREST_LIMIT}{SPIKEARREST_RATE}"

        with open(f"{BUNDLE_PATH}/apiproxy/policies/SpikeArrest.RateLimit.xml",'w') as fl:
            spikearrest_policy_template = fl.readlines()

        rtemplate = Environment(loader=BaseLoader).from_string(spikearrest_policy_template)
        spikearrest_policy = rtemplate.render({
            "identifier": SPIKEARREST_IDENTIFIER,
            "rate": SPIKEARREST_RATE
        })

        with open(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/policies/SpikeArrest.RateLimit.xml",'w') as fl:
            fl.write(spikearrest_policy)
    # end of abstraction

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

    def read_jinja_template(template_file,template_path):
        templateLoader = jinja2.FileSystemLoader(searchpath=template_path)
        templateEnv = jinja2.Environment(loader=templateLoader)
        template = templateEnv.get_template(template_file)
        return template

    logger.info(f"Creating proxy bundle zip for {API_NAME} ({STAGING_DIR})...")

    create_proxy_bundle(f"{BUNDLE_PATH}/generated/{STAGING_DIR}", API_NAME, "apiproxy")

    if not apigee.deploy_api_bundle(
        APIGEE_ENV,
        API_NAME,
        f"{BUNDLE_PATH}/{API_NAME}.zip",
        False
    ):
        logger.error(f"Deployment failed for {API_NAME} ({STAGING_DIR})")

    # body['spec']['status'] = {'apiStatus': "foobar"} 
    # TODO: update custom resource status
    logger.info(f"Deployment succeeded for {API_NAME} ({STAGING_DIR})") 

    # get hostname from environment group using API
    # concatenate the proxy base path onto the hostname

if __name__ == '__main__':
    kopf.run() 
