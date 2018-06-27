import argparse
import torch

def parse_arguments():

    # Command Line args
    parser = argparse.ArgumentParser(description='Variable Capacity Network for Continual Learning')

    parser.add_argument('--batch-size', type=int, default=64, metavar='BS',
                        help='input batch size for training (default: 64)')

    parser.add_argument('--test-batch-size', type=int, default=1000, metavar='TBS',
                        help='input batch size for testing (default: 1000)')

    parser.add_argument('--epochs', type=int, default=1, metavar='E',
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

    parser.add_argument('--log-interval', type=int, default=10, metavar='N',
                        help='how many batches to wait before logging training status')

    # [train dataset size] = [full MNIST train set (60,000)] - [validation set size]
    parser.add_argument('--train-dataset-size', type=int, default=59800, metavar='TDS',
                        help='number of images in the training dataset')

    parser.add_argument('--validation-dataset-size', type=int, default=200, metavar='VDS',
                        help='number of images in the validation dataset')

    # size of hidden layer(s)
    parser.add_argument('--hidden-size', type=int, default=30, metavar='HS',
                        help='number of neurons in each hidden layer of the network')

    return parser.parse_args()

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

def build_models():
