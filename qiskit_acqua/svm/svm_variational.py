# -*- coding: utf-8 -*-

# Copyright 2018 IBM.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================

import sys
if sys.version_info < (3,0):
    raise Exception("Please use Python version 3 or greater.")

from qiskit import QuantumProgram, QuantumRegister, ClassicalRegister, QuantumCircuit
from qiskit_acqua import QuantumAlgorithm

from functools import partial
import numpy as np
from SPSA_optimizer import SPSA_parameters, SPSA_calibration, SPSA_optimization
from cost_helpers import *
from quantum_circuit_variational import eval_cost_function, eval_cost_function_with_unlabeled_data


class SVM_Variational(QuantumAlgorithm):

    SVM_VARIATIONAL_CONFIGURATION = {
                'name': 'SVM_Variational',
                'description': 'SVM_Variational Algorithm',
                'input_schema': {
                    '$schema': 'http://json-schema.org/schema#',
                    'id': 'SVM_Variational_schema',
                    'type': 'object',
                    'properties': {
                        'num_of_qubits': {
                            'type': 'integer',
                            'default': 2,
                            'minimum': 2
                        },
                        'circuit_depth': {
                            'type': 'integer',
                            'default': 3,
                            'minimum': 3
                        },
                        'max_trials': {
                            'type': 'integer',
                            'default': 10,
                            'minimum': 10
                        }
                    },
                    'additionalProperties': False
                },
                'problems': ['svm_classification']
            }
    def __init__(self, configuration=None):
        super().__init__(configuration or self.SVM_VARIATIONAL_CONFIGURATION.copy())
        self._ret = {}




    def init_params(self, params, algo_input):
        SVMQK_params = params.get(QuantumAlgorithm.SECTION_KEY_ALGORITHM)
        self.training_dataset = algo_input.training_dataset
        self.test_dataset = algo_input.test_dataset
        self.datapoints = algo_input.datapoints
        self.class_labels = list(self.training_dataset.keys())
        self.init_args(SVMQK_params.get('num_of_qubits'), SVMQK_params.get('circuit_depth'), SVMQK_params.get('max_trials'))

    def init_args(self, num_of_qubits=2, circuit_depth=3, max_trials=250):
        self.num_of_qubits=num_of_qubits
        self.entangler_map = entangler_map_creator(num_of_qubits)
        self.coupling_map = None # the coupling_maps gates allowed on the device
        self.initial_layout = None
        self.shots=self._execute_config['shots']
        self.backend=self._backend
        self.circuit_depth=circuit_depth
        self.max_trials=max_trials

    def train(self, training_input, class_labels):
        initial_theta=np.random.randn(2 * self.num_of_qubits * (self.circuit_depth + 1))
        eval_cost_function_partial=partial(eval_cost_function, self.entangler_map, self.coupling_map, \
                                           self.initial_layout, self.num_of_qubits, self.circuit_depth, training_input, class_labels, self.backend, self.shots, True)
        SPSA_params = SPSA_parameters() # pre-computed parameters
        # SPSA_params=SPSA_calibration(eval_cost_function_partial,initial_theta,initial_c=0.1,target_update=2*np.pi*0.1, stat=25)
        cost_final, theta_Best, cost_plus, cost_minus, _, _ = SPSA_optimization(eval_cost_function_partial,initial_theta,SPSA_params, self.max_trials, 10)
        costs = [cost_final, cost_plus, cost_minus]
        return theta_Best, costs


    def test(self, theta_Best, test_input, class_labels):
        total_cost, std_cost, success_ratio, predicted_labels = eval_cost_function(self.entangler_map, self.coupling_map, self.initial_layout, self.num_of_qubits, self.circuit_depth, test_input, class_labels, self.backend, self.shots, train=False, theta=theta_Best)

        print('Classification success for this set is  %s %%  \n'%(100*success_ratio))
        return success_ratio


    def predict(self, theta_Best, input_datapoints, class_labels):
        predicted_labels = eval_cost_function_with_unlabeled_data(self.entangler_map, self.coupling_map, self.initial_layout, self.num_of_qubits, self.circuit_depth, input_datapoints, class_labels, self.backend, self.shots, train=False, theta=theta_Best)
        return predicted_labels


    def run(self):
        if self.training_dataset is None:
            self._ret['error'] = 'training dataset is missing! please provide it'
            return self._ret


        theta_Best, costs = self.train(self.training_dataset, self.class_labels)

        if self.test_dataset is not None:
            success_ratio = self.test(theta_Best, self.test_dataset, self.class_labels)
            self._ret['test_success_ratio'] = success_ratio

        if self.datapoints is not None:
            predicted_labels = self.predict(theta_Best, self.datapoints, self.class_labels)
            self._ret['predicted_labels'] = predicted_labels

        return self._ret

