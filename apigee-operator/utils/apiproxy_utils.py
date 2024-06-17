import os
from base_logger import logger
from jinja2 import Environment, BaseLoader

def create_proxy_metadata(API_NAME, STAGING_DIR, BUNDLE_PATH):
    """Creates the {API_NAME}.xml file for the API proxy.

    Args:
        API_NAME (str): The name of the API proxy.
        STAGING_DIR (str): The directory where the API proxy bundle is being staged.
        BUNDLE_PATH (str): The path to the root directory of the project.

    Returns:
        None
    """

    with open(f"{BUNDLE_PATH}/apiproxy/apiproxy.xml",'r') as fl:
        proxy_metadata_template = fl.read()
    
    rtemplate = Environment(loader=BaseLoader).from_string(proxy_metadata_template)

    proxy_metadata = rtemplate.render({
        "name": API_NAME
    })

    with open(f"{BUNDLE_PATH}/generated/{STAGING_DIR}/apiproxy/{API_NAME}.xml",'w') as fl:
        fl.write(proxy_metadata)
