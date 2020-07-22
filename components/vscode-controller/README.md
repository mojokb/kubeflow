# Vscode Controller

clone Notebook Controller

## Spec

The user needs to specify the PodSpec for the vscode.
For example:

```
apiVersion: kubeflow.org/v1alpha1
kind: Vscode
metadata:
  name: my-vscode
  namespace: test
spec:
  template:
    spec:  # Your PodSpec here
      containers:
      - image: dudaji/vscode:cap.0.0.1
        args: ["/usr/bin/code-server", "--verbose", "2", "--host", "0.0.0.0", 
               "--auth", "none", "--bind-addr", "0.0.0.0:8888", "."]
        name: vscode
      ...
```

The required fields are `containers[0].image` and (`containers[0].command` and/or `containers[0].args`).
That is, the user should specify what and how to run.
