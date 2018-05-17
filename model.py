import torch

class Model:
    def __init__(self, in_data, out_data):

        self.h1_dim = 100 # number of nodes in hidden layer 1

        self.in_dim = int(list(in_data.size())[0]) # input dimension - 784 (28 * 28) for MNIST
        self.out_dim = int(list(out_data.size())[0]) # output dimension - 10 classes (digits 0-9) for MNIST

        # Simple network with one hidden layer
        self.model = torch.nn.Sequential(
            torch.nn.Linear(self.in_dim, self.h1_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(self.h1_dim, self.out_dim),
        )

        # Define the initial loss function as simple cross entropy, as the network will first be trained
        # on a single task (no Fisher Information incorporated into the loss function).
        self.loss = torch.nn.CrossEntropyLoss()


