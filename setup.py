import argparse
import torch
import numpy as np
import scipy as sp
from EWCModel import EWCModel
from NoRegModel import NoRegModel


def parse_arguments():

    # Command Line args
    parser = argparse.ArgumentParser(description='Variable Capacity Network for Continual Learning')

    parser.add_argument('--batch-size', type=int, default=100, metavar='BS',
                        help='input batch size for training (default: 64)')

    parser.add_argument('--test-batch-size', type=int, default=1000, metavar='TBS',
                        help='input batch size for testing (default: 1000)')

    parser.add_argument('--epochs', type=int, default=3, metavar='E',
                        help='number of epochs to train (default: 1)')

    parser.add_argument('--lr', type=float, default=0.1, metavar='LR',
                        help='learning rate (default: 0.1)')

    parser.add_argument('--l2-reg-penalty', type=float, default=0.0, metavar='L2',
                        help='l2 regularization penalty (weight decay) (default: 0.0)')

    parser.add_argument('--lam', type=float, default=15, metavar='LAM',
                        help='ewc lambda value (fisher multiplier) (default: 15)')

    parser.add_argument('--momentum', type=float, default=0.0, metavar='M',
                        help='SGD momentum (default: 0.0)')

    parser.add_argument('--no-cuda', action='store_true', default=False,
                        help='disables CUDA training')

    parser.add_argument('--seed-torch', type=int, default=1, metavar='ST',
                        help='random seed for PyTorch (default: 1)')

    parser.add_argument('--seed-numpy', type=int, default=1, metavar='SN',
                        help='random seed for NumPy (default: 1)')

    parser.add_argument('--seed-scipy', type=int, default=1, metavar='SS',
                        help='random seed for SciPy (default: 1)')

    parser.add_argument('--log-interval', type=int, default=10, metavar='N',
                        help='how many batches to wait before logging training status (default 10)')

    # [train dataset size] = [full MNIST train set (60,000)] - [validation set size]
    parser.add_argument('--train-dataset-size', type=int, default=59800, metavar='TDS',
                        help='number of images in the training dataset')

    parser.add_argument('--validation-dataset-size', type=int, default=200, metavar='VDS',
                        help='number of images in the validation dataset')

    # size of hidden layer(s)
    parser.add_argument('--hidden-size', type=int, default=100, metavar='HS',
                        help='number of neurons in each hidden layer of the network')

    # 28 x 28 pixels = 784 pixels per MNIST image
    parser.add_argument('--input-size', type=int, default=784, metavar='IS',
                        help='size of each input data sampe to the network (default 784 (28 * 28))')

    # 10 classes - digits 0-9
    parser.add_argument('--output-size', type=int, default=10, metavar='OS',
                        help='size of the output of the network (default 10)')

    # e.g. 2 to double the size of the network when expansion occurs
    parser.add_argument('--scale-factor', type=int, default=2, metavar='ES',
                        help='the factor by which to scale the size of network layers upon expansion')

    return parser.parse_args()


def seed_rngs(args):

    # set a manual seed for PyTorch CPU random number generation
    torch.manual_seed(args.seed_torch)

    # set a manual seed for PyTorch GPU random number generation
    torch.cuda.manual_seed_all(args.seed_torch)

    # set a manual seed for NumPy random number generation
    np.random.seed(args.seed_numpy)

    # set a manual seed for SciPy random number generation
    sp.random.seed(args.seed_scipy)

def set_gpu_options(args):

    # determines if CUDA should be used - only if available AND not disabled via arguments
    use_cuda = not args.no_cuda and torch.cuda.is_available()

    # arguments specific to CUDA computation
    # num_workers: how many subprocesses to use for data loading - if set to 0, data will be loaded in the main process
    # pin_memory: if True, the DataLoader will copy tensors into CUDA pinned memory before returning them
    kwargs = {'num_workers': 1, 'pin_memory': True} if use_cuda else {}

    # set the device on which to perform computations - later calls to .to(device) will move tensors to GPU or CPU
    # based on the value determined here
    device = torch.device("cuda" if use_cuda else "cpu")

    return kwargs, device

def build_models(args, device):

    # Instantiate a model that will be trained using only vanilla SGD (no regularization).
    #
    # .to(device):
    #   Move all parameters and buffers in the module Net to device (CPU or GPU- set above).
    #   Both integral and floating point values are moved.
    no_reg_model = NoRegModel(
        args.hidden_size,
        args.input_size,
        args.output_size,
        device
    ).to(device)

    # Instantiate a model that will be trained using EWC.
    #
    # .to(device):
    #   Move all parameters and buffers in the module Net to device (CPU or GPU- set above).
    #   Both integral and floating point values are moved.
    ewc_model = EWCModel(
        args.hidden_size,
        args.input_size,
        args.output_size,
        device,
        lam=args.lam  # the lambda (fisher multiplier) value to be used in the EWC loss formula
    ).to(device)

    return [no_reg_model, ewc_model]