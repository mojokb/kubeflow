package metrics

import (
	"context"

	"github.com/prometheus/client_golang/prometheus"
	appsv1 "k8s.io/api/apps/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/metrics"
)

// Metrics includes metrics used in vscode controller
type Metrics struct {
	cli                      client.Client
	runningVscodes         *prometheus.GaugeVec
	VscodeCreation         *prometheus.CounterVec
	VscodeFailCreation     *prometheus.CounterVec
	VscodeCullingCount     *prometheus.CounterVec
	VscodeCullingTimestamp *prometheus.GaugeVec
}

func NewMetrics(cli client.Client) *Metrics {
	m := &Metrics{
		cli: cli,
		runningVscodes: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "vscode_running",
				Help: "Current running vscodes in the cluster",
			},
			[]string{"namespace"},
		),
		VscodeCreation: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "vscode_create_total",
				Help: "Total times of creating vscodes",
			},
			[]string{"namespace"},
		),
		VscodeFailCreation: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "vscode_create_failed_total",
				Help: "Total failure times of creating vscodes",
			},
			[]string{"namespace"},
		),
		VscodeCullingCount: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "vscode_culling_total",
				Help: "Total times of culling vscodes",
			},
			[]string{"namespace", "name"},
		),
		VscodeCullingTimestamp: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "last_vscode_culling_timestamp_seconds",
				Help: "Timestamp of the last vscode culling in seconds",
			},
			[]string{"namespace", "name"},
		),
	}

	metrics.Registry.MustRegister(m)
	return m
}

// Describe implements the prometheus.Collector interface.
func (m *Metrics) Describe(ch chan<- *prometheus.Desc) {
	m.runningVscodes.Describe(ch)
	m.VscodeCreation.Describe(ch)
	m.VscodeFailCreation.Describe(ch)
}

// Collect implements the prometheus.Collector interface.
func (m *Metrics) Collect(ch chan<- prometheus.Metric) {
	m.scrape()
	m.runningVscodes.Collect(ch)
	m.VscodeCreation.Collect(ch)
	m.VscodeFailCreation.Collect(ch)
}

// scrape gets current running vscode statefulsets.
func (m *Metrics) scrape() {
	stsList := &appsv1.StatefulSetList{}
	err := m.cli.List(context.TODO(), stsList)
	if err != nil {
		return
	}
	stsCache := make(map[string]float64)
	for _, v := range stsList.Items {
		name, ok := v.Spec.Template.GetLabels()["vscode-name"]
		if ok && name == v.Name {
			stsCache[v.Namespace] += 1
		}
	}

	for ns, v := range stsCache {
		m.runningVscodes.WithLabelValues(ns).Set(v)
	}
}
