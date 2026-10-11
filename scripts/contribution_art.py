"""Render public contribution levels with a fresh, irregular SVG snake route."""
import argparse
import datetime as dt
import html
import json
import random
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


class Calendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-date' in attrs and 'data-level' in attrs:
            self.cells[attrs['data-date']] = int(attrs['data-level'])


def render(cells, target):
    cells = sorted(cells, key=lambda c: c['date'])
    first = dt.date.fromisoformat(cells[0]['date'])
    origin = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    points = {}
    for cell in cells:
        offset = (dt.date.fromisoformat(cell['date']) - origin).days
        points[(offset // 7, offset % 7)] = cell
    rng = random.SystemRandom()
    food = {p for p, cell in points.items() if cell['level'] > 0}
    start = rng.choice(list(set(points) - food) or list(points))
    route = [start]

    def walk(source, destination):
        queue = deque([source])
        previous = {source: None}
        while queue:
            current = queue.popleft()
            if current == destination:
                steps = []
                while current != source:
                    steps.append(current)
                    current = previous[current]
                return list(reversed(steps))
            x, y = current
            neighbors = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
            rng.shuffle(neighbors)
            for neighbor in neighbors:
                if neighbor in points and neighbor not in previous:
                    previous[neighbor] = current
                    queue.append(neighbor)
        raise ValueError('Calendar cells are disconnected')

    remaining = food.copy()
    while remaining:
        x, y = route[-1]
        nearby = sorted(remaining, key=lambda p: abs(p[0]-x)+abs(p[1]-y))[:3]
        destination = rng.choice(nearby)
        for step in walk(route[-1], destination):
            route.append(step)
            remaining.discard(step)
    route += walk(route[-1], start)
    if len(route) == 1:
        route.append(start)
    first_visit = {}
    for index, point in enumerate(route):
        first_visit.setdefault(point, index)
    assert food <= set(first_visit)
    duration = max(30, min(120, (len(route)-1) * 0.24))
    path = 'M' + ' L'.join(f'{24 + x * 20},{24 + y * 20}' for x, y in route)
    last = cells[-1]['date']
    for theme in ['dark', 'light']:
        colors = ['#202923', '#34493c', '#526b57', '#788b67', '#a5ae7f'] if theme == 'dark' else ['#ebeee8', '#d7dfce', '#b5c5a4', '#889f75', '#5d7954']
        ink = '#e1b273' if theme == 'dark' else '#9d6c2e'
        width = 48 + max(p[0] for p in points) * 20
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="164" viewBox="0 0 {width} 164" role="img" aria-labelledby="t d"><title id="t">Public contribution calendar</title><desc id="d">Real contribution levels through {last}. Each green dot represents an active day. The snake consumes all active days along an irregular route, then the calendar resets.</desc>']
        static_parts = parts.copy()
        for (x, y), cell in points.items():
            tile = f'<rect x="{17+x*20}" y="{17+y*20}" width="14" height="14" rx="2" fill="{colors[0]}"><title>{html.escape(cell["date"])}: level {cell["level"]}/4</title></rect>'
            parts.append(tile)
            static_parts.append(tile)
            if cell['level'] > 0:
                dot = f'<circle cx="{24+x*20}" cy="{24+y*20}" r="5.5" fill="{colors[cell["level"]]}"><title>{html.escape(cell["date"])}: contribution level {cell["level"]}/4</title>'
                consumed = max(0.00001, first_visit[(x,y)] / (len(route)-1) * 0.96)
                parts.append(dot + f'<animate attributeName="opacity" values="1;0;0" keyTimes="0;{consumed:.7f};1" calcMode="discrete" dur="{duration:.2f}s" repeatCount="indefinite"/></circle>')
                static_parts.append(dot + '</circle>')
        static = ''.join(static_parts) + '</svg>'
        for index in range(8, -1, -1):
            radius = 6.5 if index == 0 else 4.2
            opacity = 1 if index == 0 else 0.92 - index * 0.055
            parts.append(f'<circle r="{radius}" fill="{ink}" opacity="0"><animate attributeName="opacity" values="{opacity:.2f};{opacity:.2f}" dur="{duration:.2f}s" begin="{index*0.08}s" repeatCount="indefinite"/><animateMotion path="{path}" dur="{duration:.2f}s" begin="{index*0.08}s" repeatCount="indefinite" calcMode="linear" keyPoints="0;1;1" keyTimes="0;0.96;1"/></circle>')
        target.mkdir(parents=True, exist_ok=True)
        (target / f'github-snake-{theme}.svg').write_text(''.join(parts) + '</svg>', encoding='utf-8')
        (target / f'contributions-{theme}-static.svg').write_text(static, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path)
    args = parser.parse_args()
    if args.snapshot:
        cells = json.loads(args.snapshot.read_text(encoding='utf-8'))
    else:
        request = Request('https://github.com/users/theshindesahil/contributions', headers={'User-Agent': 'GitHub-profile-art'})
        with urlopen(request, timeout=30) as response:
            calendar = Calendar()
            calendar.feed(response.read().decode('utf-8'))
        cells = [{'date': date, 'level': level} for date, level in calendar.cells.items()]
    if len(cells) < 300 or any(c['level'] not in range(5) for c in cells):
        raise ValueError('Incomplete public calendar; existing artwork will not be replaced.')
    render(cells, Path(__file__).resolve().parents[1] / 'assets')
