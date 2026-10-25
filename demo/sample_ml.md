## Machine Learning Basics
Machine learning is a branch of artificial intelligence that lets computers learn patterns from data instead of following fixed rules. A model is a mathematical function whose parameters are tuned using training data. Training means adjusting those parameters to reduce an error measure called the loss. Supervised learning uses labelled examples, such as emails marked spam or not spam, so the model can predict labels for new emails. Unsupervised learning has no labels and instead looks for structure, such as groups of similar customers. Reinforcement learning trains an agent by rewarding good actions and penalising bad ones. Overfitting happens when a model memorises the training data and fails on new data. To detect it, we hold back a validation set and compare the error on both sets. Regularisation adds a penalty for complexity and is one way to reduce overfitting. Cross validation repeats the train and validate split several times to give a more reliable estimate of performance.

## Gradient Descent
Gradient descent is an optimisation method that repeatedly moves the model parameters in the direction that reduces the loss. The learning rate controls the size of each step. A very large learning rate overshoots the minimum, while a very small one makes training slow.

## Bias and Variance
Bias is the error from overly simple assumptions, while variance is the error from sensitivity to the particular training set. High bias causes underfitting. High variance causes overfitting. Good models balance the two, which is known as the bias-variance trade-off.

## Evaluation Metrics
Accuracy is the share of predictions that are correct. Precision is the share of predicted positives that are truly positive. Recall is the share of actual positives that the model finds. The F1 score is the harmonic mean of precision and recall.
