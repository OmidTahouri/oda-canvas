# Getting started

## Install CRD
Start off with adding the CRD to the cluster
```
# pwd: oda-canvas/
kubectl apply -f charts/oda-crds/templates/oda-exposedapi-crd.yaml
```

## Install dependencies
```
# pwd: oda-canvas/apigee-operator
pip install -r requirements.txt
```

## Update Kubernetes RBAC
When running the operator outside of the cluster, you may rightly see permission errors.
A quick fix, **not suitable for real environments**, would be to add a cluster role binding for anonymous.
```
kubectl create clusterrolebinding cluster-system-anonymous --clusterrole=cluster-admin --user=system:anonymous
```
This requires an alternative correct approach.

## Run the operator
With `kopf` on your $PATH, you can run the operator locally:
```
# pwd: oda-canvas/apigee-operator
kopf run main.py --verbose
```
The Dockerfile to build the container image is a WIP.

## Add an ExposedAPI
To exercise the operator, you can add an instance of the `ExposedAPI` Custom Resource
```
kubectl apply -f product-catalog-api.yaml # note: the resource specifies the "components" namespace
```