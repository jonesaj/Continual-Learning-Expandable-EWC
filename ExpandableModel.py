import torch
import torch.nn as nn
import scipy.stats as stats
from copy import deepcopy
from torch.autograd import Variable


class ExpandableModel(nn.Module):

    def __init__(self, hidden_size, input_size, output_size, device, dataset):

        super().__init__()

        # dictionary, format:
        #  {task number: size of network parameters (weights) when the network was trained on the task}
        self.size_dictionary = {}

        # dictionary, format:
        # {task number : list of learnable parameter weight values after model trained on task}
        self.task_post_training_weights = {}

        # copy specified model hyperparameters into instance variables
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size

        self.initialize_module_list()

        self.apply(self.init_weights)

        self.device = device

        self.is_cifar = (dataset == "cifar100")


    def forward(self, x):

        # pass the data through all layers of the network
        for module in self.modulelist:
            x = module(x)

        self.y = x

        return self.y

    @classmethod
    def from_existing_model(cls, m, new_hidden_size):

        raise NotImplementedError("from_existing_model() is not implemented in ExpandableModel")

    # kwargs contains validation_loader for EWC training (needed for Fisher estimation post-training)
    def train_model(self, args, train_loader, task_number, **kwargs):

        raise NotImplementedError("train_model() is not implemented in ExpandableModel")

    def initialize_module_list(self):
        if self.is_cifar:
            self.resnet =

        else:
            self.modulelist = nn.ModuleList()

            self.modulelist.append(nn.Linear(self.input_size, self.hidden_size))
            self.modulelist.append(nn.ReLU())
            self.modulelist.append(nn.Linear(self.hidden_size, self.output_size))

    def update_size_dict(self, task_count):

        self.size_dictionary.update({task_count: self.hidden_size})

    def copy_weights_expanding(self, small_model):

        old_weights = []

        for parameter in small_model.parameters():
            old_weights.append(parameter.data.clone())
            parameter.requires_grad = False
            parameter.detach()

        for param_index, parameter in enumerate(self.parameters()):
            parameter.data[tuple(slice(0, n) for n in old_weights[param_index].shape)] = old_weights[param_index][...]

    # initialize weights in the network in the same manner as in:
    # https://github.com/ariseff/overcoming-catastrophic/blob/afea2d3c9f926d4168cc51d56f1e9a92989d7af0/model.py#L7
    @staticmethod
    def init_weights(m):

        # This function is intended to mimic the behavior of TensorFlow's tf.truncated_normal(), returning
        # a tensor of the specified shape containing values sampled from a truncated normal distribution with the
        # specified mean and standard deviation. Sampled values which fall outside of the range of +/- 2 standard deviations
        # from the mean are dropped and re-picked.
        def trunc_normal_weights(shape, mean=0.0, stdev=0.1):

            num_samples = 1

            for dim in list(shape):
                num_samples *= dim

            a, b = ((mean - 2 * stdev) - mean) / stdev, ((mean + 2 * stdev) - mean) / stdev

            samples = stats.truncnorm.rvs(a, b, scale=stdev, loc=mean, size=num_samples)

            return torch.Tensor(samples.reshape(tuple(shape)))

        if type(m) == nn.Linear:
            m.weight.data.copy_(trunc_normal_weights(m.weight.size()))
            if m.bias is not None:
                m.bias.data.fill_(0.1)

    def reset(self, task_count):
        old_weights = self.task_post_training_weights.get(task_count)

        for param_index, parameter in enumerate(self.parameters()):
            parameter.data[tuple(slice(0, n) for n in old_weights[param_index].shape)] = old_weights[param_index][...]


    def save_theta_stars(self, task_count):
        # save the theta* ("theta star") values after training - for plotting and comparative loss calculations
        # using the method in model.alternative_ewc_loss()
        #
        # NOTE: when I reference theta*, I am referring to the values represented by that variable in
        # equation (3) at:
        #   https://arxiv.org/pdf/1612.00796.pdf#section.2
        current_weights = []

        for parameter in self.parameters():
            current_weights.append(deepcopy(parameter.data.clone()))

        self.task_post_training_weights.update({task_count: deepcopy(current_weights)})

    def test(self, test_loaders, threshold):

        test_accuracies = []

        # generate a dictionary mapping tasks to models of the sizes that the network was when those tasks were
        # trained, containing subsets of the weights currently in the model (to mask new, post-expansion weights
        # when testing on tasks for which the weights did not exist during training)
        models = self.generate_model_dictionary()


        # Test the model on ALL tasks, including that on which the model was most recently trained
        for task_number, test_loader in enumerate(test_loaders):

            # from a dictionary formatted as {task number: model to use when testing that task number}, generated by
            # utils.generate_model_dictionary(), fetch the model to be used when testing this task (so as to mask
            # weights which should not be taken into consideration)
            model = models.get(task_number + 1)

            # Set the module in "evaluation mode"
            # This is necessary because some network layers behave differently when training vs testing.
            # Dropout, for example, is used to zero/mask certain weights during TRAINING (e.g. model.train())
            # to prevent overfitting. However, during TESTING/EVALUATION we do not want this to happen.
            model.eval()

            # total testing loss over all test batches for the given task_number's entire testset (sum)
            test_loss = 0

            # total number of correct predictions over the given task_number's entire testset (sum)
            correct = 0

            # Wrap in torch.no_grad() because weights have requires_grad=True (meaning pyTorch autograd knows to
            # automatically track history of computed gradients for those weights) but we don't need to track testing
            # in autograd - we are no longer training so gradients should no longer be altered/computed (only "used")
            # and therefore we don't need to track this.
            with torch.no_grad():

                # Each step of the iterator test_loader will return the following values:
                #
                # data: a 4D tensor of dimensions (test batch size, 1, 28, 28), representing the MNIST data
                # for each of the 28 x 28 = 784 pixels of each of the images in a given test batch
                #
                # target: a 1D tensor of dimension <test batch size> containing ground truth labels for each of the
                # images in the corresponding test batch in order
                for data, target in test_loader:
                    # The data needs to be wrapped in another tensor to work with our network,
                    # otherwise it is not of the appropriate dimensions... I believe this statement effectively
                    # adds a dimension.
                    #
                    # For an explanation of the meaning of this statement, see:
                    #   https://stackoverflow.com/a/42482819/9454504
                    #
                    # This code was used here in another experiment:
                    #   https://github.com/kuc2477/pytorch-ewc/blob/4a75734ef091e91a83ce82cab8b272be61af3ab6/utils.py#L75
                    data = data.view(test_loader.batch_size, -1)

                    # wrap data and target in variables- again, from the following experiment:
                    #   https://github.com/kuc2477/pytorch-ewc/blob/4a75734ef091e91a83ce82cab8b272be61af3ab6/utils.py#L76
                    #
                    # .to(device):
                    # set the device (CPU or GPU) to be used with data and target to device variable (defined in main())
                    data, target = Variable(data).to(model.device), Variable(target).to(model.device)

                    # Forward pass: compute predicted output by passing data to the model. Module objects
                    # override the __call__ operator so you can call them like functions. When
                    # doing so you pass a Tensor of input data to the Module and it produces
                    # a Tensor of output data. We have overriden forward() above, so our forward() method will be called here.
                    output = model(data)

                    # Define the testing loss to be cross entropy loss based on predicted values (output)
                    # and ground truth labels (target), calculate the testing batch loss, and sum it with the total testing
                    # loss over all batches in the given task_number's entire testset (contained within test_loss).
                    #
                    # NOTE: size_average = False:
                    # By default, the losses are averaged over observations for each minibatch.
                    # If size_average is False, the losses are summed for each minibatch. Default: True
                    #
                    # Here we use size_average = False because we want to SUM all testing batch losses and average those
                    # at the end of testing on the current task (by dividing by total number of testing SAMPLES (not batches) to obtain an
                    # average loss over all testing batches). Otherwise, if size_average == True, we would be getting average
                    # loss for each testing batch and then would average those at the end of testing on the current task
                    # to obtain average testing loss, which could theoretically result in some comparative loss of accuracy
                    # in the calculation of the final testing loss value for this task.
                    #
                    # NOTE:
                    # <some loss function>.item() gets the a scalar value held in the loss
                    criterion = nn.CrossEntropyLoss(size_average=False)
                    test_loss += criterion(output, target).item()

                    # Get the index of the max log-probability for each of the samples in the testing batch.
                    #
                    # output is a 2D tensor of dimensions (test batch size, 10) containing network-predicted probabilities
                    # that the testing input is an image of each class (digits 0-9, signified by the index of each probability
                    # in the output tensor for a given test image). That is to say that in the second dimension of output
                    # the classification probabilities might look like the following for a given image:
                    #       [0.1, 0.1, 0.05, 0.05, 0.2, 0.4, 0.1, 0.0, 0.0, 0.0]
                    # Because the sixth entry (index 5) contains the maximum value relative to all other indices, the network's
                    # prediction is that this image belongs to the sixth class- and is therefore the digit 5.
                    #
                    # NOTE: torch.max() Returns the maximum value of EACH ROW of the input tensor in the given dimension dim.
                    # The second return value is the index location of each maximum value found (argmax). This is why we use
                    # the second return value as the value of the variable pred, because we want the index of the maximum
                    # probability (not its value)- hence the [1] indexing at the end of the statement.
                    #
                    # ARGUMENTS:
                    #
                    # Using dimension 1 as the first argument allows us to get the index of the highest valued
                    # column in each row of output, which practically translates to getting the maximum predicted class
                    # probability for each sample.
                    #
                    # If keepdim is True, the output tensors are of the same size as input except in the dimension dim
                    # (first argument- in this case 1) where they are of size 1 (because we calculated ONE maximum value per
                    # row). Otherwise, dim is squeezed (see torch.squeeze()), resulting in the output tensors having 1
                    # fewer dimension than input.
                    pred = output.max(1, keepdim=True)[1]

                    # Check if predictions are correct, and if so add one to the total number of correct predictions across the
                    # entire testing set for each correct prediction.
                    #
                    # A prediction is correct if the index of the highest value in the
                    # prediction output is the same as the index of the highest value in the label for that sample.
                    #
                    # For example (MNIST):
                    #   prediction: [0.1, 0.1, 0.05, 0.05, 0.2, 0.4, 0.1, 0.0, 0.0, 0.0]
                    #   label:      [0, 0, 0, 0, 0, 1, 0, 0, 0, 0]
                    #
                    #   This would be a correct prediction- the sixth entry (index 5) in each array holds the highest
                    #   value
                    #
                    # In this case, the targets/labels are stored as scalar index values (e.g. torch.Tensor([1, 4, 5])
                    # for labels for a one, a four, and a five (in that order)
                    #
                    # tensor_X.view_as(other) returns a resulting version of tensor_X with the same size as other.size()
                    #
                    # torch.eq() -> element wise equality:
                    # tensor_X.eq(tensor_Y) returns a tensor of the same size as tensor_X with 0's at every index for which
                    # the entry at that index in tensor_X does not match the entry at that index in tensor_Y and 1's at every
                    # index for which tensor_X and tensor_Y contain matching values
                    #
                    # .sum() sums every row of the tensor into a tensor holding a single value
                    #
                    # .item() gets the scalar value held in the sum tensor
                    correct += pred.eq(target.view_as(pred)).sum().item()

            # Divide the accumulated test loss across all testing batches for the current task_number by the total number
            # of testing samples in the task_number's testset (in this case, 10,000) to get the average loss for the
            # entire test set for task_number.
            test_loss /= len(test_loader.dataset)

            # The overall accuracy of the model's predictions on the task indicated by task_number as a percent
            # value is the count of its accurate predictions divided by the number of predictions it made, all multiplied by 100
            accuracy = 100. * correct / len(test_loader.dataset)

            test_accuracies.append(accuracy)

            # For task_number's complete test set (all batches), display the average loss and accuracy
            print('\nTest set {}: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
                task_number + 1, test_loss, correct, len(test_loader.dataset),
                accuracy))

        if test_accuracies[len(test_accuracies) - 1] < threshold:
            return -1 # accuracy minimum threshold not met on most recent task

        else:
            return 0 # accuracy minimum threshold met

    # given a dictionary with task numbers as keys and model sizes (size of hidden layer(s) in the model when the model was
    # trained on a given task) as values, generate and return a dictionary correlating task numbers with model.Model
    # objects of the appropriate sizes, containing subsets of the weights currently in model
    def generate_model_dictionary(self):

        model_sizes = []

        # fetch all unique model sizes from the model size dictionary and store them in a list (model_sizes)
        for key in self.size_dictionary.keys():
            if not self.size_dictionary.get(key) in model_sizes:
                model_sizes.append(self.size_dictionary.get(key))

        models = []

        # make a model of each size specified in model_sizes, add them to models list
        for hidden_size in model_sizes:
            models.append(
                ExpandableModel(
                    hidden_size,
                    self.input_size,
                    self.output_size,
                    self.device
                ).to(self.device)
            )

        # copy weights from a larger to a smaller model - used when generating smaller models with subsets of current
        # model weights for testing the network on previous tasks...
        def copy_weights_shrinking(big_model, small_model):

            big_weights = []  # weights in parameters from the larger model

            # save data from big model
            for parameter in big_model.parameters():
                big_weights.append(parameter.data.clone())

            # transfer that data to the smaller model -
            # copy each weight from larger network that should still be in the smaller model to matching index
            # in the smaller network
            for param_index, parameter in enumerate(small_model.parameters()):
                parameter.data[...] = big_weights[param_index][tuple(slice(0, n) for n in list(parameter.size()))]

        # copy subsets of weights from the largest model to all other models
        for to_model in models:
            copy_weights_shrinking(self, to_model)

        model_dictionary = {}

        # build the model dictionary
        for model in models:
            for task_number in [k for k, v in self.size_dictionary.items() if v == model.hidden_size]:
                model_dictionary.update({task_number: model})

        return model_dictionary
