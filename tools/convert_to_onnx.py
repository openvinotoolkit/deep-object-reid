"""
 Copyright (c) 2020 Intel Corporation

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

import argparse

import onnx
import torch

from scripts.default_config import get_default_config, model_kwargs, merge_from_files_with_base
from scripts.script_utils import group_norm_symbolic
from torch.onnx.symbolic_registry import register_op

from torchreid.data.transforms import build_inference_transform
from torchreid.models import build_model
from torchreid.utils import check_isfile, load_checkpoint, load_pretrained_weights, random_image
from torchreid.integration.nncf.compression import is_checkpoint_nncf
from torchreid.integration.nncf.compression_script_utils import (make_nncf_changes_in_eval,
                                                                 make_nncf_changes_in_main_training_config)


def parse_num_classes(source_datasets, classification=False, num_classes=None, snap_path=None):
    if classification:
        if snap_path is not None:
            chkpt = load_checkpoint(snap_path)
            num_classes_from_snap = chkpt['num_classes'] if 'num_classes' in chkpt else None

            if isinstance(num_classes_from_snap, int):
                num_classes_from_snap = [num_classes_from_snap]

            if num_classes is None:
                num_classes = num_classes_from_snap
            else:
                print('Warning: number of classes in model was overriden via command line')
        assert num_classes is not None and len(num_classes) > 0

    if num_classes is not None and len(num_classes) > 0:
        return num_classes

    num_clustered = 0
    num_rest = 0
    for src in source_datasets:
        if isinstance(src, (tuple, list)):
            num_clustered += 1
        else:
            num_rest += 1

    total_num_sources = num_clustered + int(num_rest > 0)
    assert total_num_sources > 0

    return [0] * total_num_sources  # dummy number of classes


def reset_config(cfg):
    cfg.model.download_weights = False


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--config-file', type=str, default='',
                        help='Path to config file')
    parser.add_argument('--output-name', type=str, default='model',
                        help='Path to save ONNX model')
    parser.add_argument('--num-classes', type=int, nargs='+', default=None)
    parser.add_argument('--opset', type=int, default=9)
    parser.add_argument('--verbose', default=False, action='store_true',
                        help='Verbose mode for onnx.export')
    parser.add_argument('--disable-dyn-axes', default=False, action='store_true')
    parser.add_argument('opts', default=None, nargs=argparse.REMAINDER,
                        help='Modify config options using the command-line')
    args = parser.parse_args()

    cfg = get_default_config()
    cfg.use_gpu = torch.cuda.is_available()
    if args.config_file:
        merge_from_files_with_base(cfg, args.config_file)
    reset_config(cfg)
    cfg.merge_from_list(args.opts)

    is_nncf_used = is_checkpoint_nncf(cfg.model.load_weights)
    if is_nncf_used:
        print(f'Using NNCF -- making NNCF changes in config')
        cfg = make_nncf_changes_in_main_training_config(cfg, args.opts)
    cfg.freeze()

    num_classes = parse_num_classes(cfg.data.sources, cfg.model.classification, args.num_classes, cfg.model.load_weights)
    model = build_model(**model_kwargs(cfg, num_classes))
    load_pretrained_weights(model, cfg.model.load_weights)

    if is_nncf_used:
        print('Begin making NNCF changes in model')
        model = make_nncf_changes_in_eval(model, cfg)
        print('End making NNCF changes in model')

    model.eval()

    transform = build_inference_transform(
        cfg.data.height,
        cfg.data.width,
        norm_mean=cfg.data.norm_mean,
        norm_std=cfg.data.norm_std,
    )

    input_img = random_image(cfg.data.height, cfg.data.width)
    input_blob = transform(input_img).unsqueeze(0)

    input_names = ['data']
    output_names = ['reid_embedding']
    if not args.disable_dyn_axes:
        dynamic_axes = {'data': {0: 'batch_size', 1: 'channels', 2: 'height', 3: 'width'},
                        'reid_embedding': {0: 'batch_size', 1: 'dim'}}
    else:
        dynamic_axes = {}

    output_file_path = args.output_name
    if not args.output_name.endswith('.onnx'):
        output_file_path += '.onnx'

    register_op("group_norm", group_norm_symbolic, "", args.opset)
    with torch.no_grad():
        torch.onnx.export(
            model,
            input_blob,
            output_file_path,
            verbose=args.verbose,
            export_params=True,
            input_names=input_names,
            output_names=output_names,
            dynamic_axes=dynamic_axes,
            opset_version=args.opset,
            operator_export_type=torch.onnx.OperatorExportTypes.ONNX
        )

    net_from_onnx = onnx.load(output_file_path)
    try:
        onnx.checker.check_model(net_from_onnx)
        print('ONNX check passed.')
    except onnx.onnx_cpp2py_export.checker.ValidationError as ex:
        print('ONNX check failed: {}.'.format(ex))


if __name__ == '__main__':
    main()
