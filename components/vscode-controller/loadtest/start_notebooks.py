# This script aims to load test Kubeflow Vscode controller by starting
# certain nubmer of Kubeflow Vscode custom resources.
#
# Before the test, make sure you have connected to your desired Kubeflow cluster
# and have enough Kubernetes resources (or have autoscaling turned on).
#
# To start the load test, you can run
#   python3.8 start_vscodes.py -l <#vscodes> -n <namespace>
#
# After the test, you can delete the resources via the following command
#   python3.8 start_vscodes.py -l <#vscodes> -n <namespace> -p delete

import argparse
import subprocess
import yaml

parser = argparse.ArgumentParser(
    description='Validate all URLs in the kubeflow.org website'
)

parser.add_argument(
    '-l',
    '--load',
    dest='num_vscodes',
    nargs='?',
    default=3,
    type=int,
    help='Number of vscodes to start the load test. (Default: %(default)s)',
)

parser.add_argument(
    '-n',
    '--namespace',
    dest='namespace',
    nargs='?',
    default='kubeflow',
    help='Namespace to start the workload. (Default: %(default)s)',
)

parser.add_argument(
    '-p',
    '--operation',
    dest='operation',
    nargs='?',
    default='apply',
    help='\'apply\' or \'delete\'. (Default: %(default)s)',
)


def write_vscode_config(config, name, num):
  config['metadata']['name'] = 'jupyter-test-' + str(num)
  config['spec']['template']['spec']['containers'][0]['name'
                                                     ] = 'vscode-' + str(num)
  config['spec']['template']['spec']['volumes'][0]['persistentVolumeClaim'][
      'claimName'] = 'test-vol-' + str(num)
  with open(name, 'w') as f:
    print(yaml.dump(config), file=f)


def write_pvc_config(config, name, num):
  config['metadata']['name'] = 'test-vol-' + str(num)
  with open(name, 'w') as f:
    print(yaml.dump(config), file=f)


def main():
  args = parser.parse_args()
  assert args.operation == 'apply' or args.operation == 'delete'
  vscode_config = None
  pvc_config = None
  with open('jupyter_test.yaml', 'r') as f:
    vscode_config = yaml.safe_load(f.read())
  with open('jupyter_pvc.yaml', 'r') as f:
    pvc_config = yaml.safe_load(f.read())
  for i in range(args.num_vscodes):
    vscode_name = f'jupyter_test_{i}.yaml'
    pvc_name = f'jupyter_pvc_{i}.yaml'
    write_vscode_config(vscode_config, vscode_name, i)
    write_pvc_config(pvc_config, pvc_name, i)
    print(f'kubectl {args.operation} -f {vscode_name} ...')
    subprocess.run([
        'kubectl', args.operation, '-f', vscode_name, '-n', args.namespace
    ],
                   capture_output=True,
                   check=True)
    print(f'kubectl {args.operation} -f {pvc_name} ...')
    subprocess.run([
        'kubectl', args.operation, '-f', pvc_name, '-n', args.namespace
    ],
                   capture_output=True,
                   check=True)


if __name__ == '__main__':
  main()
