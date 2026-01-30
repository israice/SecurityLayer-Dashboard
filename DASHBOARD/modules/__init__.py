# Shared config for modules
import os
import yaml

script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(script_dir, '..', 'config.yaml')

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

REPO_ROOT = os.path.normpath(os.path.join(script_dir, '..'))
ENCODING = config['ENCODING']
