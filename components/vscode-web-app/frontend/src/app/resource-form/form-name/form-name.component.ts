import { Component, OnInit, OnDestroy, Input } from "@angular/core";
import {
  FormGroup,
  ValidatorFn,
  AbstractControl,
  Validators
} from "@angular/forms";
import { KubernetesService } from "src/app/services/kubernetes.service";
import { NamespaceService } from "src/app/services/namespace.service";
import { Subscription } from "rxjs";

@Component({
  selector: "app-form-name",
  templateUrl: "./form-name.component.html",
  styleUrls: ["./form-name.component.scss", "../resource-form.component.scss"]
})
export class FormNameComponent implements OnInit, OnDestroy {
  subscriptions = new Subscription();
  vscodes: Set<string> = new Set<string>();
  @Input() parentForm: FormGroup;

  constructor(private k8s: KubernetesService, private ns: NamespaceService) {}

  ngOnInit() {
    // Add the ExistingName validator to the list if it doesn't already exist
    this.parentForm
      .get("name")
      .setValidators([Validators.required, this.existingName()]);

    // Keep track of the existing Vscodes in the selected Namespace
    // Use these names to check if the input name exists
    const nsSub = this.ns.getSelectedNamespace().subscribe(ns => {
      this.k8s.getResource(ns).subscribe(vscodes => {
        this.vscodes.clear();
        vscodes.map(nb => this.vscodes.add(nb.name));
      });
    });

    this.subscriptions.add(nsSub);
  }

  ngOnDestroy() {
    this.subscriptions.unsubscribe();
  }

  showNameError() {
    const nameCtrl = this.parentForm.get("name");

    if (nameCtrl.hasError("existingName")) {
      return `Vscode Server "${nameCtrl.value}" already exists`;
    } else {
      return "The Vscode Server's name can't be empty";
    }
  }

  private existingName(): ValidatorFn {
    return (control: AbstractControl): { [key: string]: any } => {
      const exists = this.vscodes.has(control.value);
      return exists ? { existingName: true } : null;
    };
  }
}
