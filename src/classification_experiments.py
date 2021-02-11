from copy import deepcopy
from types import SimpleNamespace
from typing import Tuple, List, Dict

import numpy as np
import torch
from context_printer import Color
from context_printer import ContextPrinter as Ctp

from src.architectures import BinaryClassifier, NormalizingModel
from src.classification_ml import multitrain_classifiers, multitest_classifiers
from src.data import device_names
from src.federated_util import federated_averaging
from src.general_ml import set_models_sub_divs
from src.metrics import BinaryClassificationResults, compute_sum_results
from src.print_util import print_federation_round, print_rates
from src.supervised_data import get_all_supervised_dls, get_train_test_dls, get_new_dl_test


def local_classifiers_train_val(train_data: List[List[Dict[str, np.ndarray]]], val_data: List[List[Dict[str, np.ndarray]]], args: SimpleNamespace) \
        -> List[BinaryClassificationResults]:
    # Creating the dataloaders
    clients_dl_train, clients_dl_val = get_train_test_dls(train_data, val_data, args.train_bs, args.test_bs)

    # Initialize the models and compute the normalization values with each client's local training data
    n_clients = len(args.clients_devices)
    models = [NormalizingModel(BinaryClassifier(activation_function=args.activation_fn, hidden_layers=args.hidden_layers),
                               sub=torch.zeros(args.n_features), div=torch.ones(args.n_features)) for _ in range(n_clients)]
    set_models_sub_divs(args, models, clients_dl_train, color=Color.RED)

    # Training
    multitrain_classifiers(trains=list(zip(['Training client {} on: '.format(i + 1) + device_names(client_devices)
                                            for i, client_devices in enumerate(args.clients_devices)],
                                           clients_dl_train, models)),
                           args=args, main_title='Training the clients', color=Color.GREEN)

    # Local testing
    results = multitest_classifiers(tests=list(zip(['Validating client {} on: '.format(i + 1) + device_names(client_devices)
                                                    for i, client_devices in enumerate(args.clients_devices)],
                                                   clients_dl_val, models)),
                                    main_title='Validating the clients on their own devices', color=Color.BLUE)
    results_sum = compute_sum_results(results)
    Ctp.print('Average results')
    print_rates(results_sum)

    return results


def local_classifiers_train_test(train_data: List[List[Dict[str, np.ndarray]]], local_test_data: List[List[Dict[str, np.ndarray]]],
                                 new_test_data: List[Dict[str, np.ndarray]], args: SimpleNamespace) \
        -> Tuple[BinaryClassificationResults, BinaryClassificationResults]:
    # Creating the dataloaders
    clients_dl_train, clients_dl_test = get_train_test_dls(train_data, local_test_data, args.train_bs, args.test_bs)
    new_dl_test = get_new_dl_test(new_test_data, args.test_bs)

    # Initialize the models and compute the normalization values with each client's local training data
    n_clients = len(args.clients_devices)
    models = [NormalizingModel(BinaryClassifier(activation_function=args.activation_fn, hidden_layers=args.hidden_layers),
                               sub=torch.zeros(args.n_features), div=torch.ones(args.n_features)) for _ in range(n_clients)]
    set_models_sub_divs(args, models, clients_dl_train, color=Color.RED)

    # Training
    multitrain_classifiers(trains=list(zip(['Training client {} on: '.format(i + 1) + device_names(client_devices)
                                            for i, client_devices in enumerate(args.clients_devices)],
                                           clients_dl_train, models)),
                           args=args, main_title='Training the clients', color=Color.GREEN)

    # Local testing
    results = multitest_classifiers(tests=list(zip(['Testing client {} on: '.format(i + 1) + device_names(client_devices)
                                                    for i, client_devices in enumerate(args.clients_devices)],
                                                   clients_dl_test, models)),
                                    main_title='Testing the clients on their own devices', color=Color.BLUE)
    local_result = compute_sum_results(results)
    Ctp.print('Average results')
    print_rates(local_result)

    # New devices testing
    results = multitest_classifiers(
        tests=list(zip(['Testing client {} on: '.format(i + 1) + device_names(args.test_devices) for i in range(n_clients)],
                       [new_dl_test for _ in range(n_clients)], models)),
        main_title='Testing the clients on the new devices: ' + device_names(args.test_devices),
        color=Color.DARK_CYAN)
    new_devices_result = compute_sum_results(results)
    Ctp.print('Average results')
    print_rates(new_devices_result)

    return local_result, new_devices_result


def federated_classifiers_train_test(train_data: List[List[Dict[str, np.ndarray]]], local_test_data: List[List[Dict[str, np.ndarray]]],
                                     new_test_data: List[Dict[str, np.ndarray]], args: SimpleNamespace) \
        -> Tuple[List[BinaryClassificationResults], List[BinaryClassificationResults]]:
    # Creating the dataloaders
    clients_dl_train, clients_dl_test = get_train_test_dls(train_data, local_test_data, args.train_bs, args.test_bs)
    new_dl_test = get_new_dl_test(new_test_data, args.test_bs)

    # Initialization of a global model
    n_clients = len(args.clients_devices)
    global_model = NormalizingModel(BinaryClassifier(activation_function=args.activation_fn, hidden_layers=args.hidden_layers),
                                    sub=torch.zeros(args.n_features), div=torch.ones(args.n_features))
    models = [deepcopy(global_model) for _ in range(n_clients)]
    set_models_sub_divs(args, models, clients_dl_train, color=Color.RED)

    # Initialization of the results
    local_results, new_devices_results = [], []

    for federation_round in range(args.federation_rounds):
        print_federation_round(federation_round, args.federation_rounds)

        # Local training of each client
        multitrain_classifiers(trains=list(zip(['Training client {} on: '.format(i + 1) + device_names(client_devices)
                                                for i, client_devices in enumerate(args.clients_devices)],
                                               clients_dl_train, models)),
                               args=args, lr_factor=(args.gamma_round ** federation_round),
                               main_title='Training the clients', color=Color.GREEN)

        # Federated averaging
        federated_averaging(global_model, models)

        # Distribute the global model back to each client
        models = [deepcopy(global_model) for _ in range(n_clients)]

        # Global model testing on each client's data
        results = multitest_classifiers(tests=list(zip(['Testing global model on: ' + device_names(client_devices)
                                                        for client_devices in args.clients_devices],
                                                       clients_dl_test, [global_model for _ in range(n_clients)])),
                                        main_title='Testing the global model on data from all clients', color=Color.BLUE)
        local_result = compute_sum_results(results)
        local_results.append(local_result)
        Ctp.print('Average results')
        print_rates(local_result)

        # Global model testing on new devices
        results = multitest_classifiers(
            tests=list(zip(['Testing global model on: ' + device_names(args.test_devices)], [new_dl_test], [global_model])),
            main_title='Testing the global model on the new devices: ' + device_names(args.test_devices),
            color=Color.DARK_CYAN)
        new_devices_result = compute_sum_results(results)
        new_devices_results.append(new_devices_result)
        Ctp.print('Average results')
        print_rates(new_devices_result)

        Ctp.exit_section()

    return local_results, new_devices_results
