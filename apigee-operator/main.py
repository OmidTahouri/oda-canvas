import kopf

@kopf.on.create('oda.tmforum.org', 'v1beta3', 'exposedapis')
def create_exposedapi_handler(body, spec, **kwargs):
    # Access API name
    api_name = body['metadata']['name']

    # extract API name
    # extract API base path
    # extract policy enforcements (ratelimiting, JWT verification, x)
    # pull in proxy template (.zip)
    # override template with CR values
    # deploy proxy
    # update CR with URL to reach proxy
    # demo: curl the URL

    print(f"ExposedAPI '{api_name}' created!")
    

if __name__ == '__main__':
    kopf.run() 
