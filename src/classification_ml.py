from copy import deepcopy

import torch
import torch.nn as nn

from architectures import NormalizingModel, BinaryClassifier
from data import get_sub_div
from metrics import StatisticsMeter, BinaryClassificationResults
from print_util import print_train_classifier, print_train_classifier_header, Color, print_rates, ContextPrinter, Columns


def train_classifier(model, num_epochs, train_loader, optimizer, criterion, scheduler, ctp: ContextPrinter):
    ctp.add_bar(Color.GRAY)
    print_train_classifier_header(ctp)
    model.train()

    num_elements = len(train_loader.dataset)
    num_batches = len(train_loader)
    batch_size = train_loader.batch_size

    for epoch in range(num_epochs):
        ctp.add_header('[{}/{}]'.format(epoch + 1, num_epochs).ljust(Columns.SMALL))
        accuracy = StatisticsMeter()
        lr = optimizer.param_groups[0]['lr']

        for i, (data, label) in enumerate(train_loader):
            output = model(data)
            loss = criterion(output, label)
            optimizer.zero_grad()
            loss.mean().backward()
            optimizer.step()

            predictions = torch.gt(output, torch.tensor(0.5)).int()
            success = torch.eq(predictions, label).float()

            start = i * batch_size
            end = start + batch_size
            if i == num_batches - 1:
                end = num_elements

            accuracy.update(success.mean(), end-start)
            if i % 1000 == 0:
                print_train_classifier(i, len(train_loader), accuracy.avg, lr, ctp, persistent=False)

        print_train_classifier(len(train_loader), len(train_loader), accuracy.avg, lr, ctp, persistent=True)

        scheduler.step()
        if optimizer.param_groups[0]['lr'] <= 1e-3:
            break
        ctp.remove_header()
    ctp.remove_header()


def test_classifier(model, test_loader):
    with torch.no_grad():
        model.eval()

        num_elements = len(test_loader.dataset)
        num_batches = len(test_loader)
        batch_size = test_loader.batch_size

        predictions = torch.zeros(num_elements)
        results = BinaryClassificationResults()

        for i, (data, label) in enumerate(test_loader):
            output = model(data)

            pred = torch.gt(output, torch.tensor(0.5)).int()
            results.add_tp(torch.logical_and(torch.eq(pred, label), label.bool()).int().sum())
            results.add_tn(torch.logical_and(torch.eq(pred, label), torch.logical_not(label.bool())).int().sum())
            results.add_fp(torch.logical_and(torch.logical_not(torch.eq(pred, label)), torch.logical_not(label.bool())).int().sum())
            results.add_fn(torch.logical_and(torch.logical_not(torch.eq(pred, label)), label.bool()).int().sum())

            start = i * batch_size
            end = start + batch_size
            if i == num_batches - 1:
                end = num_elements

            predictions[start:end] = pred.squeeze()

        return results


def set_models_sub_divs(args, models, clients_dl_train, ctp: ContextPrinter, color=Color.NONE):
    ctp.print('Computing the normalization values for each client', color=color, bold=True)
    ctp.add_bar(color)
    n_clients = len(clients_dl_train)
    for i, (model, dl_train) in enumerate(zip(models, clients_dl_train)):
        ctp.print('[{}/{}] computing normalization with {} train samples'.format(i + 1, n_clients, len(dl_train.dataset)))
        sub, div = get_sub_div(dl_train.dataset[:][0], normalization=args.normalization)
        model.set_sub_div(sub, div)
    ctp.remove_header()


# trains should be a list of tuples (title, dataloader, model) (or a zip of the lists: titles, dataloaders, models)
# this function will train each model on its associated dataloader, and will print the title for it
# lr_factor is used to multiply the lr that is contained in args (and that should remain constant)
def multitrain_classifiers(trains, args, ctp: ContextPrinter, lr_factor=1.0, main_title='Multitrain classifiers', color=Color.NONE):
    ctp.print(main_title, color=color, bold=True)
    ctp.add_bar(color)

    if type(trains) == zip:
        trains = list(trains)

    criterion = nn.BCELoss()
    for i, (title, dataloader, model) in enumerate(trains):
        ctp.print('[{}/{}] '.format(i + 1, len(trains)) + title, bold=True)
        optimizer = args.optimizer(model.parameters(), **args.optimizer_params)
        for param_group in optimizer.param_groups:
            param_group['lr'] = param_group['lr'] * lr_factor

        scheduler = args.lr_scheduler(optimizer, **args.lr_scheduler_params)

        train_classifier(model, args.epochs, dataloader, optimizer, criterion, scheduler, ctp)
        if i != len(trains)-1:
            ctp.print()
    ctp.remove_header()


# tests should be a list of tuples (title, dataloader, model) (or a zip of the lists: titles, dataloaders, models)
# this function will test each model on its associated dataloader, and will print the title for it
def multitest_classifiers(tests, ctp: ContextPrinter, main_title='Multitest classifiers', color=Color.NONE):
    ctp.print(main_title, color=color, bold=True)
    ctp.add_bar(color)

    if type(tests) == zip:
        tests = list(tests)

    results = BinaryClassificationResults()
    for i, (title, dataloader, model) in enumerate(tests):
        ctp.print('[{}/{}] '.format(i + 1, len(tests)) + title)
        results += test_classifier(model, dataloader)
        print_rates(results, ctp)
        ctp.print()

    ctp.print('Average results')
    print_rates(results, ctp)
    ctp.remove_header()
