# code written but not currently being used in the experiment...

def train(model, args, device, train_loader, epoch, task_number):
    # Set the module in "training mode"
    # This is necessary because some network layers behave differently when training vs testing.
    # Dropout, for example, is used to zero/mask certain weights during TRAINING to prevent overfitting.
    # However, during TESTING (e.g. model.eval()) we do not want this to happen.
    model.train()

    # Set the optimization algorithm for the model- in this case, Stochastic Gradient Descent with/without
    # momentum (depends on the value of args.momentum- default is 0.0, so no momentum by default).
    #
    # ARGUMENTS (in order):
    #     params (iterable) – iterable of parameters to optimize or dicts defining parameter groups
    #     lr (float) – learning rate
    #     momentum (float, optional) – momentum factor (default: 0)
    #
    # NOTE on params:
    #   model.parameters() returns an iterator over a list of the model parameters in the same order in
    #   which they appear in the network when traversed input -> output
    #   (e.g.
    #       [weights b/w input and first hidden layer,
    #        bias b/w input and hidden layer 1,
    #        ... ,
    #        weights between last hidden layer and output,
    #        bias b/w hidden layer and output]
    #   )
    optimizer = optim.SGD(model.parameters(), lr=args.lr, momentum=args.momentum)

    # Enumerate will keep an automatic loop counter and store it in batch_idx.
    # The (data, target) pair returned by DataLoader train_loader each iteration consists
    # of an MNIST image data sample and an associated label classifying it as a digit 0-9.
    #
    # The image data for the batch is represented as a 4D torch tensor (see train_loader definition in main())
    # with dimensions (batch size, 1, 28, 28)- containing a normalized floating point value for the color of
    # each pixel in each image in the batch (MNIST images are 28 x 28 pixels).
    #
    # The target is represented as a torch tensor containing the digit classification labels for
    # the training data as follows:
    #       [ 3,  4,  2,  9,  7] represents ground truth labels for a 3, a 4, a 2, a 9, and a 7.
    # NOTE:
    # The indices are converted to one-hot label representations inside of the loss function:
    #       [[0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
    #        [0, 0, 1, 0, 0, 0, 0, 0, 0, 0]]
    # represents labels for a 5 and a 2, because 1's are at index 5 and 2 in rows 0 and 1, respectively.
    #
    # SOURCE:
    # https://discuss.pytorch.org/t/why-does-the-minimal-pytorch-tutorial-not-have-mnist-images-be-onehot-for-logistic-regression/12562/6
    for batch_idx, (data, target) in enumerate(train_loader):

        # For some reason, the data needs to be wrapped in another tensor to work with our network,
        # otherwise it is not of the appropriate dimensions... I believe these two statements effectively add
        # a dimension.
        #
        # For an explanation of the meaning of these statements, see:
        #   https://stackoverflow.com/a/42482819/9454504
        #
        # This code was used here in another experiment:
        # https://github.com/kuc2477/pytorch-ewc/blob/4a75734ef091e91a83ce82cab8b272be61af3ab6/train.py#L35
        data_size = len(data)
        data = data.view(data_size, -1)

        # wrap data and target in variables- again, from the following experiment:
        #   https://github.com/kuc2477/pytorch-ewc/blob/4a75734ef091e91a83ce82cab8b272be61af3ab6/train.py#L50
        #
        # .to(device):
        #   set the device (CPU or GPU) to be used with data and target to device variable (defined in main())
        data, target = Variable(data).to(device), Variable(target).to(device)

        # Gradients are automatically accumulated- therefore, they need to be zeroed out before the next backward
        # pass through the network so that they are replaced by newly computed gradients at later training iterations,
        # rather than SUMMED with those future gradients. The reasoning behind this approach and the need to zero
        # gradients manually with each training minibatch is presented here in more detail:
        # https://discuss.pytorch.org/t/why-do-we-need-to-set-the-gradients-manually-to-zero-in-pytorch/4903/9
        #
        # From PyTorch examples:
        #   Before the backward pass, use the optimizer object to zero all of the
        #   gradients for the variables it will update (which are the learnable
        #   weights of the model). This is because by default, gradients are
        #   accumulated in buffers( i.e, not overwritten) whenever .backward()
        #   is called.
        optimizer.zero_grad()

        # forward pass: compute predicted output by passing data to the network
        # NOTE: we have overridden forward() in class Net above, so this will call model.forward()
        output = model(data)

        # Define the training loss function for the model to be cross entropy loss based on predicted values
        # and ground truth labels. This loss function only takes into account loss on the most recent task.
        #
        # NOTE: torch.nn.CrossEntropyLoss combines torch.nn.LogSoftmax() and torch.nn.NLLLoss() in one single class.
        criterion = nn.CrossEntropyLoss()

        # apply the loss function to the predictions/labels for this batch to compute loss
        loss = criterion(output, target)

        # if the model is using EWC, the summed loss term from the EWC equation must be calculated and
        # added to the loss that will be minimized by the optimizer.
        #
        # See equation (3) at:
        #   https://arxiv.org/pdf/1612.00796.pdf#section.2
        if model.ewc and task_number > 1:
            loss += ewc_loss_prev_tasks(model)

        # Backward pass: compute gradient of the loss with respect to model
        # parameters
        loss.backward()

        # Simplified abstraction provided by PyTorch which uses a single statement to update all model parameters
        # according to gradients (with respect to the last loss function on which .backward() was called and
        # optimization function's update rule.
        # In the case of SGD (without momentum), essentially executes the following:
        #
        #       with torch.no_grad():
        #           for param in model.parameters():
        #               param -= learning_rate * param.grad
        optimizer.step()

        # Each time the batch index is a multiple of the specified progress display interval (args.log_interval),
        # print a message indicating progress AND which network (model) is reporting values.
        if batch_idx % args.log_interval == 0:
            print('{} Task: {} Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                'EWC' if model.ewc else 'SGD + DROPOUT', task_number,
                epoch, batch_idx * len(data), len(train_loader.dataset), 100. * batch_idx / len(train_loader),
                loss.item()))


# THE "OLD" WAY OF COMPUTING THIS...
# This method relies on the logic here:
#   https://github.com/kuc2477/pytorch-ewc/blob/4a75734ef091e91a83ce82cab8b272be61af3ab6/model.py#L56
def compute_fisher(model, device, validation_loader):
    # a list of log_likelihoods sampled from the model output when the input is
    # a sample from the validation dataset
    loglikelihoods = []

    # for every data sample in the validation set (default 1024)...
    for data, target in validation_loader:
        # For some reason, the data needs to be wrapped in another tensor to work with our network,
        # otherwise it is not of the appropriate dimensions... I believe this statement effectively adds
        # a dimension.
        #
        # For an explanation of the meaning of this statement, see:
        #   https://stackoverflow.com/a/42482819/9454504
        #
        # This code was used here in another experiment:
        # https://github.com/kuc2477/pytorch-ewc/blob/4a75734ef091e91a83ce82cab8b272be61af3ab6/model.py#L61
        data = data.view(validation_loader.batch_size, -1)

        # wrap data and target in variables- again, from the following experiment:
        #   https://github.com/kuc2477/pytorch-ewc/blob/4a75734ef091e91a83ce82cab8b272be61af3ab6/model.py#L62
        #
        # .to(device):
        # set the device (CPU or GPU) to be used with data and target to device variable (defined in main())
        data, target = Variable(data).to(device), Variable(target).to(device)

        loglikelihoods.append(
            F.log_softmax(model(data))[range(validation_loader.batch_size), target.data]
        )

    # concatenate loglikelihood tensors in list loglikelihoods along 0th (default) dimension,
    # then calculate the mean of each row of the resulting tensor along the 0th dimension
    loglikelihood = torch.cat(loglikelihoods).mean(0)

    # here are the parameter gradients with respect to log likelihood
    loglikelihood_grads = torch.autograd.grad(loglikelihood, model.parameters())

    # list of Fisher Information Matrix diagonals
    model.fisher = []

    # see equation (2) at:
    #   https://arxiv.org/pdf/1605.04859.pdf#subsection.2.1
    for grad in loglikelihood_grads:
        model.fisher.append(torch.pow(grad, 2.0))



def save_theta_stars(model):

    # list of tensors used for saving optimal weights after most recent task training
    model.theta_stars = []

    # get the current values of each model parameter as tensors and add them to the list
    # self.theta_stars
    for parameter in model.parameters():
        model.theta_stars.append(parameter.data.clone())



def calculate_ewc_loss_prev_tasks(model):

    losses = []

    for parameter_index, parameter in enumerate(model.parameters()):


        theta_star = Variable(model.theta_stars[parameter_index])
        fisher = Variable(model.list_of_FIMs[parameter_index])

        # adjust the size of parameters to match theta_star values for the parameters if they already don't -
        # this is to account for a scenario in which expansion has just occurred and we are now calculating ewc loss
        # during training of the expanded network- the movement of weights in the new (expanded) network that
        # did not exist in the smaller network should NOT factor into the loss for this particular task and should
        # move freely. when theta stars are re-saved after training, movement of these weights will THEN be factored
        # into the loss function because we want to restrict their movements.

        # NOTE: IT IS ABSOLUTELY CRITICAL THAT WE DO NOT USE parameter.data HERE- IT RUINS EWC ACCURACY BECAUSE
        # IT IS NOT TRACKED BY PYTORCH'S AUTOGRAD...
        theta_star_size = theta_star.size()

        dim_0_indices = torch.arange(theta_star_size[0], dtype=torch.long)

        parameter_as_theta_star_size = torch.index_select(parameter, 0, dim_0_indices)

        if len(theta_star_size) > 1:
            dim_1_indices = torch.arange(theta_star_size[1], dtype=torch.long)

            parameter_as_theta_star_size = torch.index_select(parameter_as_theta_star_size, 1, dim_1_indices)

        losses.append((fisher * ((parameter_as_theta_star_size - theta_star) ** 2)).sum())

    return (model.lam / 2.0) * sum(losses)
