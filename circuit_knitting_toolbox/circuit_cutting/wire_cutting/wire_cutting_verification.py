import pickle
import argparse
import glob
from typing import Sequence, Dict, Union, Tuple, List

import numpy as np
from nptyping import NDArray
from qiskit import QuantumCircuit
from qiskit.circuit import Qubit
from qiskit.quantum_info import Statevector

from circuit_knitting_toolbox.circuit_cutting.wire_cutting.wire_cutting_evaluation import (
    evaluate_circuit,
)
from circuit_knitting_toolbox.utils.conversion import quasi_to_real
from circuit_knitting_toolbox.utils.metrics import (
    chi2_distance,
    MSE,
    MAPE,
    cross_entropy,
    HOP,
)


def verify(
    full_circuit: QuantumCircuit,
    unordered: Sequence[float],
    complete_path_map: Dict[Qubit, Sequence[Dict[str, Union[int, Qubit]]]],
    subcircuits: Sequence[QuantumCircuit],
    smart_order: Sequence[int],
) -> Tuple[NDArray, Dict[str, Dict[str, float]]]:
    ground_truth = evaluate_circuit(
        circuit=full_circuit, backend="statevector_simulator"
    )
    """
    Reorder the probability distribution
    """
    subcircuit_out_qubits: Dict[int, List[Qubit]] = {
        subcircuit_idx: [] for subcircuit_idx in smart_order
    }
    for input_qubit in complete_path_map:
        path = complete_path_map[input_qubit]
        output_qubit = path[-1]
        subcircuit_out_qubits[output_qubit["subcircuit_idx"]].append(
            (output_qubit["subcircuit_qubit"], full_circuit.qubits.index(input_qubit))
        )
    for subcircuit_idx in subcircuit_out_qubits:
        subcircuit_out_qubits[subcircuit_idx] = sorted(
            subcircuit_out_qubits[subcircuit_idx],
            key=lambda x: subcircuits[subcircuit_idx].qubits.index(x[0]),
            reverse=True,
        )
        subcircuit_out_qubits[subcircuit_idx] = [
            x[1] for x in subcircuit_out_qubits[subcircuit_idx]
        ]
    # print('subcircuit_out_qubits:',subcircuit_out_qubits)
    unordered_qubit: List[int] = []
    for subcircuit_idx in smart_order:
        unordered_qubit += subcircuit_out_qubits[subcircuit_idx]
    # print('CutQC out qubits:',unordered_qubit)
    reconstructed_output = np.zeros(len(unordered))
    for unordered_state, unordered_p in enumerate(unordered):
        bin_unordered_state = bin(unordered_state)[2:].zfill(full_circuit.num_qubits)
        _, ordered_bin_state = zip(
            *sorted(zip(unordered_qubit, bin_unordered_state), reverse=True)
        )
        ordered_bin_state_str = "".join([str(x) for x in ordered_bin_state])
        ordered_state = int(ordered_bin_state_str, 2)
        ground_p = ground_truth[ordered_state]
        reconstructed_output[ordered_state] = unordered_p
    reconstructed_output = np.array(reconstructed_output)

    metrics = {}
    for quasi_conversion_mode in ["nearest", "naive"]:
        real_probability = quasi_to_real(
            quasiprobability=reconstructed_output, mode=quasi_conversion_mode
        )

        chi2 = chi2_distance(target=ground_truth, obs=real_probability)
        mse = MSE(target=ground_truth, obs=real_probability)
        mape = MAPE(target=ground_truth, obs=real_probability)
        ce = cross_entropy(target=ground_truth, obs=real_probability)
        hop = HOP(target=ground_truth, obs=real_probability)
        metrics[quasi_conversion_mode] = {
            "chi2": chi2,
            "Mean Squared Error": mse,
            "Mean Absolute Percentage Error": mape,
            "Cross Entropy": ce,
            "HOP": hop,
        }
    return reconstructed_output, metrics
