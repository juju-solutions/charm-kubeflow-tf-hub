from pathlib import Path

from charmhelpers.core import hookenv
from charms.reactive import set_flag, clear_flag, data_changed
from charms.reactive import when, when_not, when_any

from charms import layer


@when('charm.kubeflow-tf-hub.started')
def charm_ready():
    layer.status.active('')


@when('ambassador.available')
def charm_ready(annotations):
    print(annotations)
    config = hookenv.config()
    config['kubernetes-service-annotations'] = "a=b c=d"
    config.save()


@when_any('layer.docker-resource.jupyterhub-image.changed',
          'config.change')
def update_image():
    clear_flag('charm.kubeflow-tf-hub.started')


@when('layer.docker-resource.jupyterhub-image.available')
@when_not('charm.kubeflow-tf-hub.started')
def start_charm():
    layer.status.maintenance('configuring container')

    config = hookenv.config()
    image_info = layer.docker_resource.get_info('jupyterhub-image')
    application_name = hookenv.service_name()
    jh_config_src = Path('files/jupyterhub_config.py')
    jh_config_dst = Path('/etc/config/jupyterhub_config.py')

    layer.caas_base.pod_spec_set({
        'containers': [
            {
                'name': 'tf-hub',
                'imageDetails': {
                    'imagePath': image_info.registry_path,
                    'username': image_info.username,
                    'password': image_info.password,
                },
                'command': [
                    'jupyterhub',
                    '-f',
                    str(jh_config_dst),
                ],
                'ports': [
                    {
                        'name': 'hub',
                        'containerPort': 8000,
                    },
                    {
                        'name': 'api',
                        'containerPort': 8081,
                    },
                ],
                'config': {
                    # we have to explicitly specify the k8s service name for
                    # use in the API URL because otherwise JupyterHub uses the
                    # pod name, which in our case doesn't just happen to match
                    # the service name; the k8s service name will always be the
                    # application name with a "juju-" prefix
                    'K8S_SERVICE_NAME': 'juju-{}'.format(application_name),
                    'AUTHENTICATOR': config['authenticator'],
                    'NOTEBOOK_STORAGE_SIZE': config['notebook-storage-size'],
                    'NOTEBOOK_STORAGE_CLASS': config['notebook-storage-class'],
                    'CLOUD_NAME': '',  # is there a way to detect this?
                    'REGISTRY': config['notebook-image-registry'],
                    'REPO_NAME': config['notebook-image-repo-name'],
                },
                'files': [
                    {
                        'name': 'configs',
                        'mountPath': str(jh_config_dst.parent),
                        'files': {
                            'jupyterhub_config.py': jh_config_src.read_text(),
                        },
                    },
                ],
            },
        ],
    })

    layer.status.maintenance('creating container')
    set_flag('charm.kubeflow-tf-hub.started')
