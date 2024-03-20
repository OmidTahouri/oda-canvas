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

APIGEE_ORG = "caramel-medley"
APIGEE_ENV = "test-env"
BUNDLE_PATH = os.path.dirname(os.path.abspath(__file__))

apigee = Apigee(
    apigee_type = "x",
    org = APIGEE_ORG
)

@kopf.on.create('oda.tmforum.org', 'v1beta3', 'exposedapis')
def create_exposedapi_handler(body, spec, **kwargs):
    print(f"ExposedAPI created")

    API_NAME = body['metadata']['name']
    API_BASE_PATH = body['spec']['path']
    API_TARGET_URL = body['spec']['implementation']

    SPIKEARREST_REQUIRED = body['spec']['rateLimit']['enabled']

    if SPIKEARREST_REQUIRED == True:
        logger.info("ExposedAPI resource requests rateLimit. Creating SpikeArrest policy...")

        spikearrest_policy_template = """
<SpikeArrest continueOnError="false" enabled="true" name="SpikeArrest.RateLimit">
    <Identifier ref="{{ identifier }}" />
    <Rate>{{ rate }}</Rate>
    <UseEffectiveCount>true</UseEffectiveCount>
</SpikeArrest>
        """

        rtemplate = Environment(loader=BaseLoader).from_string(spikearrest_policy_template)
        spikearrest_policy = rtemplate.render({
            "identifier": "proxy.client.ip", # from CR
            "rate": "10ps" # from CR
        })

        with open(f"{BUNDLE_PATH}/apiproxy/policies/SpikeArrest.RateLimit.xml",'w') as fl:
            fl.write(spikearrest_policy)

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

    logger.info("Creating proxy bundle zip...")
    create_proxy_bundle(f"{BUNDLE_PATH}", API_NAME, "apiproxy")

    if not apigee.deploy_api_bundle(
        APIGEE_ENV,
        API_NAME,
        f"{BUNDLE_PATH}/{API_NAME}.zip",
        False
    ):
        logger.error(f"Deployment failed for proxy: {API_NAME}")

    # body['spec']['status'] = {'apiStatus': "foobar"} 

    # TODO: update custom resource status
    logger.info(f"Deployment succeeded for proxy: {API_NAME}") 


    # extract policy enforcements (ratelimiting, JWT verification, x)
    # override template with CR values
    # update CR with URL to reach proxy
    # demo: curl the URL
    

if __name__ == '__main__':
    kopf.run() 
