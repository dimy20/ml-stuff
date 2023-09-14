#! venv/bin/python3

import numpy as np
import time
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import math

x_train = np.array([[2104, 5, 1, 45], [1416, 3, 2, 40], [852, 2, 1, 35]])
y_train = np.array([460, 232, 178])

b_init = 785.1811367994083
w_init = np.array([ 0.39133535, 18.75376741, -53.36032453, -26.42131618])

#feature_names = ['size(sqft)','bedrooms','floors','age']

def compute_cost(x : np.ndarray, y: np.ndarray, w: np.ndarray, b: np.float32):
    sum = 0
    #n = number of rows = number of input vectors
    n = len(x) 
    for i in range(0, n):
        #predict for each x-vector.
        f_wb = np.dot(x[i], w) + b
        #error
        err = (f_wb - y[i]) ** 2
        sum += err

    return sum / (n * 2)

def compute_gradient(x_inputs : np.ndarray, y: np.ndarray, w: np.ndarray, b: np.float32):
    partial_w = np.zeros(w.shape)
    partial_b = 0

    num_inputs = x_inputs.shape[0]
    num_features = x_inputs.shape[1]

    #compute gradient for the weights
    for i in range(0, num_inputs):
        #out prediction
        fwb = np.dot(w, x_inputs[i]) + b
        for j in range(0, num_features):
            # one vector of m features and computing the prediction with out model
            # x * w + b => we multiply each weight against each feature
            partial_w[j] += (fwb - y[i]) * x_inputs[i][j]

        partial_b += fwb - y[i]

    partial_w /= num_inputs
    partial_b /= num_inputs

    return partial_w, partial_b

x_axis = []

def gradient_descent(x, y, w_in, b_in: float, learning_rate, num_iters):
    w = np.copy(w_in)
    b : float = b_in

    cost_history = []
    print_freq = math.ceil(num_iters / 10)

    for i in range(0, num_iters):
        if i < 100000 and i % print_freq == 0:
            cost = compute_cost(x, y, w, b)
            cost_history.append(cost)
            x_axis.append(i)
            print(f"Iteration {i:4d}: Cost {cost_history[-1]:8.2f}")

        w_update, b_update = compute_gradient(x, y, w, b)
        w = w - learning_rate * w_update
        b = b - learning_rate * b_update

    return w, b, cost_history

def znormalize(x):
    #take the mean of each feature aka: compute the mean per column:
    mean = np.mean(x, axis=0)
    #take the standartd deviation of each feature aka: compute the std deviation per column:
    std_deviation = np.std(x, axis=0)
    # apply the z normalization to each feature: (x - mu / sgma) 
    #numpy takes care of doing this operation component-wise for each input vector.
    return (x - mean) / std_deviation

def main():
    iterations = 200
    #learning_rate = 5.0e-7
    learning_rate = 0.1
    nx_train = znormalize(x_train)
    w_final, b_final, history = gradient_descent(nx_train, y_train, np.zeros_like(w_init), 0., learning_rate, iterations)

    plt.plot(x_axis, history)
    plt.xlabel("iterations")
    plt.ylabel("cost")

    #test
    m,_ = x_train.shape
    for i in range(m):
        print(f"prediction: {np.dot(nx_train[i], w_final) + b_final:0.2f}, target value: {y_train[i]}")

    plt.show()

if __name__ == '__main__':
    main()
