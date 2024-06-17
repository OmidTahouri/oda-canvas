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
from utils.apiproxy_utils import create_proxy_metadata

# TODO: abstract these top-level variables
APIGEE_ORG = "caramel-medley"
APIGEE_ENV = "dev"

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


    # extract core properties from CR
    API_NAME = body['metadata']['name'] # or body['spec']['name']?
    UNIQUE_ID = body['metadata']['uid']
    RESOURCE_VERSION = body['metadata']['resourceVersion']
    TARGET_URL = body['spec']['implementation']
    BASE_PATH = body['spec']['path']

    STAGING_DIR = f"{UNIQUE_ID}-{RESOURCE_VERSION}"

    os.makedirs(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/policies")
    os.makedirs(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/proxies")
    os.makedirs(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/targets")

    create_proxy_metadata(API_NAME, STAGING_DIR, BUNDLE_PATH)

    # TODO: abstract the following logic to util file, like create_proxy_metadata()

    # create spike arrest policy
    SPIKE_ARREST_REQUIRED = body['spec']['rateLimit']['enabled']
    SPIKE_ARREST_STEP = ""

    if SPIKE_ARREST_REQUIRED == True:
        logger.info(f"Creating SpikeArrest policy for {API_NAME} ({STAGING_DIR})...")

        SPIKE_ARREST_IDENTIFIER = body['spec']['rateLimit']['identifier']
        SPIKE_ARREST_LIMIT = body['spec']['rateLimit']['limit']
        SPIKE_ARREST_INTERVAL = body['spec']['rateLimit']['interval']
        SPIKE_ARREST_RATE = f"{SPIKE_ARREST_LIMIT}{SPIKE_ARREST_INTERVAL}"

        with open(f"{BUNDLE_PATH}/apiproxy/policies/SpikeArrest.RateLimit.xml",'r') as fl:
            spike_arrest_policy_template = fl.read()

        rtemplate = Environment(loader=BaseLoader).from_string(spike_arrest_policy_template)
        spike_arrest_policy = rtemplate.render({
            "identifier": SPIKE_ARREST_IDENTIFIER,
            "rate": SPIKE_ARREST_RATE
        })

        with open(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/policies/SpikeArrest.RateLimit.xml",'w') as fl:
            fl.write(spike_arrest_policy)
        
        SPIKE_ARREST_STEP = "<Step><Name>SpikeArrest.RateLimit</Name></Step>"
    # end of spike arrest policy

    # create verify api key policy
    VERIFY_API_KEY_REQUIRED = body['spec']['apiKeyVerification']['enabled']
    VERIFY_API_KEY_STEP = ""

    if VERIFY_API_KEY_REQUIRED == True:
        logger.info(f"Creating VerifyAPIKey policy for {API_NAME} ({STAGING_DIR})...")

        API_KEY_LOCATION = body['spec']['apiKeyVerification']['location']

        with open(f"{BUNDLE_PATH}/apiproxy/policies/VerifyAPIKey.Validate.xml",'r') as fl:
            verify_api_key_policy_template = fl.read()

        rtemplate = Environment(loader=BaseLoader).from_string(verify_api_key_policy_template)

        verify_api_key_policy = rtemplate.render({
            "location": API_KEY_LOCATION
        })

        with open(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/policies/VerifyAPIKey.Validate.xml",'w') as fl:
            fl.write(verify_api_key_policy)

        VERIFY_API_KEY_STEP = "<Step><Name>VerifyAPIKey.Validate</Name></Step>"
    # end of verify api key policy

    # create proxy endpoint
    with open(f"{BUNDLE_PATH}/apiproxy/proxies/default.xml",'r') as fl:
        proxy_endpoint_template = fl.read()
    
    rtemplate = Environment(loader=BaseLoader).from_string(proxy_endpoint_template)

    proxy_endpoint = rtemplate.render({
        "base_path": BASE_PATH,
        "spike_arrest_step": SPIKE_ARREST_STEP,
        "verify_api_key_step": VERIFY_API_KEY_STEP 
    })

    with open(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/proxies/default.xml",'w') as fl:
        fl.write(proxy_endpoint)
    # end of proxy endpoint

    # create target endpoint
    with open(f"{BUNDLE_PATH}/apiproxy/targets/default.xml",'r') as fl:
        target_endpoint_template = fl.read()
    
    rtemplate = Environment(loader=BaseLoader).from_string(target_endpoint_template)

    target_endpoint = rtemplate.render({
        "target_url": TARGET_URL
    })

    with open(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/targets/default.xml",'w') as fl:
        fl.write(target_endpoint)
    # end of target endpoint

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

    create_proxy_bundle(f"{BUNDLE_PATH}/generated/{STAGING_DIR}", API_NAME, f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy")

    if not apigee.deploy_api_bundle(
        APIGEE_ENV,
        API_NAME,
        f"{BUNDLE_PATH}/generated/{STAGING_DIR}/{API_NAME}.zip",
        True
    ):
        logger.error(f"Deployment failed for {API_NAME} ({STAGING_DIR})")

    # body['spec']['status'] = {'apiStatus': "foobar"} 
    # TODO: update custom resource status
    logger.info(f"Deployment succeeded for {API_NAME} ({STAGING_DIR})") 

    # get hostname from environment group using API
    # concatenate the proxy base path onto the hostname

if __name__ == '__main__':
    kopf.run() 
