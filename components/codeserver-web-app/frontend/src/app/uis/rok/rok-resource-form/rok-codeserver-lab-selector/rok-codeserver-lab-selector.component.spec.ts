import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { RokCodeserverLabSelectorComponent } from './rok-codeserver-lab-selector.component';

describe('RokCodeserverLabSelectorComponent', () => {
  let component: RokCodeserverLabSelectorComponent;
  let fixture: ComponentFixture<RokCodeserverLabSelectorComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ RokCodeserverLabSelectorComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(RokCodeserverLabSelectorComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
