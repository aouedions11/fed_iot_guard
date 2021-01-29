import torch
import torch.nn as nn
from context_printer import Color
from context_printer import ContextPrinter as Ctp

from metrics import BinaryClassificationResults
from print_util import print_train_classifier, print_train_classifier_header, print_rates, Columns


def train_classifier(model, num_epochs, train_loader, optimizer, criterion, scheduler):
    Ctp.enter_section(color=Color.DARK_GRAY)
    print_train_classifier_header()
    model.train()

    for epoch in range(num_epochs):
        Ctp.enter_section(header='[{}/{}]'.format(epoch + 1, num_epochs).ljust(Columns.SMALL))
        lr = optimizer.param_groups[0]['lr']
        results = BinaryClassificationResults()
        for i, (data, label) in enumerate(train_loader):
            output = model(data)
            loss = criterion(output, label)
            optimizer.zero_grad()
            loss.mean().backward()
            optimizer.step()

            pred = torch.gt(output, torch.tensor(0.5)).int()
            results.update(pred, label)

            if i % 1000 == 0:
                print_train_classifier(i, len(train_loader), results, lr, persistent=False)

        print_train_classifier(len(train_loader), len(train_loader), results, lr, persistent=True)

        scheduler.step()
        if optimizer.param_groups[0]['lr'] <= 1e-3:
            break
        Ctp.exit_section()
    Ctp.exit_section()


def test_classifier(model, test_loader):
    with torch.no_grad():
        model.eval()
        results = BinaryClassificationResults()
        for i, (data, label) in enumerate(test_loader):
            output = model(data)

            pred = torch.gt(output, torch.tensor(0.5)).int()
            results.update(pred, label)

        return results


# trains should be a list of tuples (title, dataloader, model) (or a zip of the lists: titles, dataloaders, models)
# this function will train each model on its associated dataloader, and will print the title for it
# lr_factor is used to multiply the lr that is contained in args (and that should remain constant)
def multitrain_classifiers(trains, args, lr_factor=1.0, main_title='Multitrain classifiers', color=Color.NONE):
    Ctp.enter_section(main_title, color)

    if type(trains) == zip:
        trains = list(trains)

    criterion = nn.BCELoss()
    for i, (title, dataloader, model) in enumerate(trains):
        Ctp.print('[{}/{}] '.format(i + 1, len(trains)) + title, bold=True)
        optimizer = args.optimizer(model.parameters(), **args.optimizer_params)
        for param_group in optimizer.param_groups:
            param_group['lr'] = param_group['lr'] * lr_factor

        scheduler = args.lr_scheduler(optimizer, **args.lr_scheduler_params)

        train_classifier(model, args.epochs, dataloader, optimizer, criterion, scheduler)
        if i != len(trains)-1:
            Ctp.print()
    Ctp.exit_section()


# tests should be a list of tuples (title, dataloader, model) (or a zip of the lists: titles, dataloaders, models)
# this function will test each model on its associated dataloader, and will print the title for it
def multitest_classifiers(tests, main_title='Multitest classifiers', color=Color.NONE):
    Ctp.enter_section(main_title, color)

    if type(tests) == zip:
        tests = list(tests)

    results = BinaryClassificationResults()
    for i, (title, dataloader, model) in enumerate(tests):
        Ctp.print('[{}/{}] '.format(i + 1, len(tests)) + title)
        results += test_classifier(model, dataloader)
        print_rates(results)
        Ctp.print()

    Ctp.print('Average results')
    print_rates(results)
    Ctp.exit_section()
