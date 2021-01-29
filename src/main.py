import itertools
import sys
from types import SimpleNamespace

import torch
import torch.utils.data
from context_printer import Color
from context_printer import ContextPrinter as Ctp

from anomaly_detection_experiments import local_autoencoders, federated_autoencoders
from classification_experiments import local_classifiers, federated_classifiers
from data import get_dataframes


def run_grid_search(experiment_function, constant_args: dict, varying_args: dict):
    # Loading the data
    device_id_to_dataframes = get_dataframes(Color.YELLOW)
    Ctp.print('\n')

    args = constant_args
    product = list(itertools.product(*varying_args.values()))
    for i, experiment_args_tuple in enumerate(product):
        experiment_args = {key: arg for (key, arg) in zip(varying_args.keys(), experiment_args_tuple)}
        args.update(experiment_args)
        Ctp.enter_section('Experiment [{}/{}] with args: '.format(i + 1, len(product)) + str(experiment_args), color=Color.BLINK)
        experiment_function(device_id_to_dataframes, args=SimpleNamespace(**args))
        Ctp.exit_section()
        Ctp.print('\n')


def main(experiment='single_classifier'):
    common_params = {'n_features': 115,
                     'normalization': 'min-max',
                     'test_bs': 4096}

    autoencoder_params = {'hidden_layers': [86, 58, 38, 29, 38, 58, 86],
                          'activation_fn': torch.nn.ELU}

    classifier_params = {'hidden_layers': [40, 10, 5],
                         'activation_fn': torch.nn.ELU}

    multiple_clients_params = {'clients_devices': [[0], [1], [2], [3], [4], [5], [6], [7]],
                               'test_devices': [8]}

    single_client_params = {'clients_devices': [[0, 1, 2, 3, 4, 5, 6, 7]],
                            'test_devices': [8]}

    autoencoder_opt_default_params = {'epochs': 0,
                                      'train_bs': 64,
                                      'optimizer': torch.optim.Adadelta,
                                      'optimizer_params': {'lr': 1.0, 'weight_decay': 5 * 1e-5},
                                      'lr_scheduler': torch.optim.lr_scheduler.ReduceLROnPlateau,
                                      'lr_scheduler_params': {'patience': 3, 'threshold': 1e-2, 'factor': 0.5, 'verbose': False}}

    autoencoder_opt_federated_params = {'epochs': 0,
                                        'train_bs': 64,
                                        'optimizer': torch.optim.Adadelta,
                                        'optimizer_params': {'lr': 1.0, 'weight_decay': 5 * 1e-5},
                                        'lr_scheduler': torch.optim.lr_scheduler.StepLR,
                                        'lr_scheduler_params': {'step_size': 1, 'gamma': 0.9},
                                        'federation_rounds': 3,
                                        'gamma_round': 0.5}

    classifier_opt_default_params = {'epochs': 0,
                                     'train_bs': 64,
                                     'optimizer': torch.optim.Adadelta,
                                     'optimizer_params': {'lr': 1.0, 'weight_decay': 1e-5},
                                     'lr_scheduler': torch.optim.lr_scheduler.StepLR,
                                     'lr_scheduler_params': {'step_size': 1, 'gamma': 0.5}}

    classifier_opt_federated_params = {'epochs': 0,
                                       'train_bs': 64,
                                       'optimizer': torch.optim.Adadelta,
                                       'optimizer_params': {'lr': 1.0, 'weight_decay': 1e-5},
                                       'lr_scheduler': torch.optim.lr_scheduler.StepLR,
                                       'lr_scheduler_params': {'step_size': 1, 'gamma': 0.5},
                                       'federation_rounds': 5,
                                       'gamma_round': 0.5}

    if experiment == 'single_autoencoder':
        Ctp.print('\n\t\t\t\t\tSINGLE AUTOENCODER GRID SEARCH\n', bold=True)
        run_grid_search(local_autoencoders,
                        {**common_params, **autoencoder_params, **autoencoder_opt_default_params, **single_client_params},
                        {'normalization': ['0-mean 1-var', 'min-max'], 'hidden_layers': [[20, 5, 20], [86, 58, 38, 29, 38, 58, 86]]})

    elif experiment == 'multiple_autoencoders':
        Ctp.print('\n\t\t\t\t\tMULTIPLE AUTOENCODERS GRID SEARCH\n', bold=True)
        run_grid_search(local_autoencoders,
                        {**common_params, **autoencoder_params, **autoencoder_opt_default_params, **multiple_clients_params},
                        {'normalization': ['min-max']})

    elif experiment == 'federated_autoencoders':
        Ctp.print('\n\t\t\t\t\tFEDERATED AUTOENCODERS GRID SEARCH\n', bold=True)
        run_grid_search(federated_autoencoders,
                        {**common_params, **autoencoder_params, **autoencoder_opt_federated_params, **multiple_clients_params},
                        {'normalization': ['min-max']})

    elif experiment == 'single_classifier':
        Ctp.print('\n\t\t\t\t\tSINGLE CLASSIFIER GRID SEARCH\n', bold=True)
        run_grid_search(local_classifiers,
                        {**common_params, **classifier_params, **classifier_opt_default_params, **single_client_params},
                        {'normalization': ['min-max']})

    elif experiment == 'multiple_classifiers':
        Ctp.print('\n\t\t\t\t\tMULTIPLE CLASSIFIERS GRID SEARCH\n', bold=True)
        run_grid_search(local_classifiers,
                        {**common_params, **classifier_params, **classifier_opt_default_params, **multiple_clients_params},
                        {'normalization': ['min-max']})

    elif experiment == 'federated_classifiers':
        Ctp.print('\n\t\t\t\t\tFEDERATED CLASSIFIERS GRID SEARCH\n', bold=True)
        run_grid_search(federated_classifiers,
                        {**common_params, **classifier_params, **classifier_opt_federated_params, **multiple_clients_params},
                        {'normalization': ['min-max']})


# TODO: each experiment function should return some results to be able to know with which arguments it performed the best
# TODO: make a test function that should use the test set only and test a specific set of parameters
# TODO: improve the dataloading so that it can either get its data for training and validation or for training and testing
#  the first case would be used by the grid search function, the second would be used by the test params function
#  assuming 10% of the dataset is left out for test, the first case would make its train/opt splits from the first 90% of the dataset
#  while the second case would take the whole 90% of the dataset as train set and the remaining 10% as test set
# TODO: idea leave an unused set between train set and test set so that the test set is not too much dependent on the train set
# TODO: rework get_splits so that you can give a list of proportions as input instead of just the number of splits


if __name__ == "__main__":
    main(sys.argv[1])
