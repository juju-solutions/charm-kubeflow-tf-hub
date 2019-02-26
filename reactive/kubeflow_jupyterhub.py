from pathlib import Path
from glob import glob

import yaml
from charmhelpers.core import hookenv
from charms.reactive import set_flag, clear_flag
from charms.reactive import when, when_not, when_any

from charms import layer


@when('charm.kubeflow-jupyterhub.started')
def charm_ready():
    layer.status.active('')


@when_any('layer.docker-resource.jupyterhub-image.changed',
          'config.change')
def update_image():
    clear_flag('charm.kubeflow-jupyterhub.started')


@when('layer.docker-resource.jupyterhub-image.available')
@when_not('charm.kubeflow-jupyterhub.started')
def start_charm():
    layer.status.maintenance('configuring container')

    config = hookenv.config()
    image_info = layer.docker_resource.get_info('jupyterhub-image')
    service_name = hookenv.service_name()

    hub_port = 8000
    api_port = 8081

    pip_installs = [
        'jhub-remote-user-authenticator',
        'jupyterhub-dummyauthenticator',
        'jupyterhub-kubespawner',
        'oauthenticator',
    ]

    layer.caas_base.pod_spec_set({
        'service': {
            'annotations': {
                'getambassador.io/config': yaml.dump_all([
                    {
                        'apiVersion': 'ambassador/v0',
                        'kind':  'Mapping',
                        'name':  'tf_hub',
                        'prefix': '/hub/',
                        'rewrite': '/hub/',
                        'service': f'{service_name}:{hub_port}',
                        'use_websocket': True,
                        'timeout_ms': 30000,
                    },
                    {
                        'apiVersion': 'ambassador/v0',
                        'kind':  'Mapping',
                        'name':  'tf_hub_user',
                        'prefix': '/user/',
                        'rewrite': '/user/',
                        'service': f'{service_name}:{hub_port}',
                        'timeout_ms': 30000,
                    },
                ]),
            },
        },
        'containers': [
            {
                'name': 'jupyterhub',
                'imageDetails': {
                    'imagePath': image_info.registry_path,
                    'username': image_info.username,
                    'password': image_info.password,
                },
                # TODO: Move to init containers to pip install when juju supports it
                'command': [
                    'bash',
                    '-c',
                    f'pip install {" ".join(pip_installs)} && jupyterhub -f /etc/config/jupyterhub_config.py',
                ],
                'ports': [
                    {
                        'name': 'hub',
                        'containerPort': hub_port,
                    },
                    {
                        'name': 'api',
                        'containerPort': api_port,
                    },
                ],
                'config': {
                    'K8S_SERVICE_NAME': service_name,
                    'AUTHENTICATOR': config['authenticator'],
                    'NOTEBOOK_STORAGE_SIZE': config['notebook-storage-size'],
                    'NOTEBOOK_STORAGE_CLASS': config['notebook-storage-class'],
                    'NOTEBOOK_IMAGE': config['notebook-image'],
                },
                'files': [
                    {
                        'name': 'configs',
                        'mountPath': '/etc/config',
                        'files': {
                            Path(filename).name: Path(filename).read_text()
                            for filename in glob('files/*')
                        },
                    },
                ],
            },
        ],
    })

    layer.status.maintenance('creating container')
    set_flag('charm.kubeflow-jupyterhub.started')
