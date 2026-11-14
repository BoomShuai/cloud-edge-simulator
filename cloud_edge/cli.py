import argparse
import csv
from dataclasses import asdict
import json
from pathlib import Path
import sys
from .core import Task, Node, Link, CollaborativeSimulator, default_nodes, default_links, research_workload, strategy_catalog, summarize


def load_scenario(path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('Scenario exceeds 1 MiB')
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema') != 1:
        raise ValueError('Unsupported scenario schema')
    tasks = [Task(**item) for item in value['tasks']]
    if not 1 <= len(tasks) <= 10000:
        raise ValueError('Expected 1..10000 tasks')
    return tasks, [Node(**item) for item in value['nodes']], [Link(**item) for item in value['links']]


def scenario_document(variant=0):
    return {'schema': 1, 'scope': 'Synthetic analytic scenario, not hardware measurements',
            'tasks': [asdict(item) for item in research_workload(variant)],
            'nodes': [asdict(item) for item in default_nodes()],
            'links': [asdict(item) for item in default_links()]}


def run(tasks, nodes, links, selected):
    simulator = CollaborativeSimulator(nodes, links)
    strategies = strategy_catalog()
    results = {}
    for name in selected:
        decisions = simulator.run(tasks, strategies[name])
        results[name] = {'summary': summarize(decisions), 'decisions': [asdict(item) for item in decisions]}
    return {'schema': 1, 'units': {'latency': 'ms', 'energy': 'J', 'input_output': 'decimal MB'},
            'scope': 'Independent tasks with fixed per-node queue delay; no queue evolution, real scheduling or hardware execution.',
            'results': results}


def save_report(directory, report):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    with (directory / 'summary.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['strategy','tasks','avg_latency_ms','p95_latency_ms','deadline_hit_rate','total_energy_j'])
        for name, value in report['results'].items():
            summary = value['summary']
            writer.writerow([name]+[summary[key] for key in ['tasks','avg_latency_ms','p95_latency_ms','deadline_hit_rate','total_energy_j']])
    rows = ['# Synthetic placement comparison','', '| Strategy | Mean ms | Deadline hit rate | Energy J |','| --- | ---: | ---: | ---: |']
    for name, value in report['results'].items():
        s = value['summary'];rows.append(f"| {name} | {s['avg_latency_ms']} | {s['deadline_hit_rate']} | {s['total_energy_j']} |")
    rows += ['', report['scope']]
    (directory / 'report.md').write_text('\n'.join(rows)+'\n', encoding='utf-8')


def main(argv=None):
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Synthetic cloud-edge-device placement experiments')
    parser.add_argument('command', choices=['demo','run','scenario'])
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--variant', type=int, default=0)
    parser.add_argument('--strategy', choices=['all',*strategy_catalog()], default='all')
    args = parser.parse_args(argv)
    try:
        if args.command == 'scenario':
            if args.output is None: raise ValueError('Scenario needs a new output JSON path')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8') as stream:
                json.dump(scenario_document(args.variant), stream, ensure_ascii=False, indent=2, allow_nan=False)
            print(json.dumps({'created': True, 'synthetic': True}));return 0
        if args.command == 'run':
            if args.input is None: raise ValueError('Run needs --input')
            tasks, nodes, links = load_scenario(args.input)
        else:
            tasks, nodes, links = research_workload(args.variant), default_nodes(), default_links()
        selected = list(strategy_catalog()) if args.strategy == 'all' else [args.strategy]
        report = run(tasks, nodes, links, selected)
        if args.output: save_report(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False));return 0
    except (OSError, ValueError, TypeError, KeyError):
        print('Simulation failed: check scenario schema, positive capacities, complete links and a new output path.', file=sys.stderr)
        return 2
