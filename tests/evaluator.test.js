import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { parseConfigYaml, STARTER_WEEKLY_ITEMS } from '../js/configLoader.js';
import {
  getEvaluationHorizon,
  evaluateHomeworkForDate,
  getQuickDateChips
} from '../js/evaluator.js';
import homeworkHandler from '../api/homework.js';

describe('Phase 1 & 2: Config & Homework Evaluation Engine', () => {
  it('parses config.yaml with Kid -> Classes mapping', () => {
    const raw = fs.readFileSync(path.join(process.cwd(), 'config.yaml'), 'utf8');
    const config = parseConfigYaml(raw);
    expect(config.kids.Isaac.color).toBe('blue');
    expect(config.kids.Isaac.classes).toContain('Math Competition');
    expect(config.kids.Asher.color).toBe('green');
    expect(config.kids.Asher.classes).toContain('Piano');
  });

  it('on Thursday (2026-10-22), evaluates Thursday + Friday for weekly and 3-day lookahead for upcoming', () => {
    const horizon = getEvaluationHorizon('2026-10-22', 3);
    expect(horizon.refWeekday).toBe('Thursday');
    expect(horizon.weeklyTargetDates.map(d => d.weekday)).toEqual(['Thursday', 'Friday']);
    expect(horizon.upcomingEndDate).toBe('2026-10-25');

    const sampleItems = [
      ...STARTER_WEEKLY_ITEMS,
      {
        id: 'up-1',
        kid: 'Isaac',
        class: 'French',
        type: 'upcoming',
        title: 'Past Test (Should Hide)',
        due: '2026-10-21',
        active: true
      },
      {
        id: 'up-2',
        kid: 'Isaac',
        class: 'History',
        type: 'upcoming',
        title: 'Rome Essay',
        due: '2026-10-25', // Within 3 days
        active: true
      },
      {
        id: 'up-3',
        kid: 'Asher',
        class: 'Science',
        type: 'upcoming',
        title: 'Far Future Lab',
        due: '2026-10-30', // More than 3 days out
        active: true
      }
    ];

    const res = evaluateHomeworkForDate(sampleItems, '2026-10-22');
    const titles = res.tasks.map(t => t.raw_title);

    // Thursday weekly (Isaac Math Comp) + Friday weekly (Asher Spelling & Workbook)
    expect(titles).toContain('Work Packet 1 Hour!');
    expect(titles).toContain('Spelling Test');
    expect(titles).toContain('Workbook Pages');
    // Wednesday weekly should NOT show on Thursday
    expect(titles).not.toContain('Trad Spelling');
    // Upcoming within 3 days shows; past due & >3 days out do NOT show
    expect(titles).toContain('Rome Essay');
    expect(titles).not.toContain('Past Test (Should Hide)');
    expect(titles).not.toContain('Far Future Lab');
  });

  it('on Friday (2026-10-23), skips Sat/Sun and includes Friday + Monday assignments', () => {
    const res = evaluateHomeworkForDate(STARTER_WEEKLY_ITEMS, '2026-10-23');
    const titles = res.tasks.map(t => t.raw_title);

    // Friday items (Asher Spelling & Workbook)
    expect(titles).toContain('Spelling Test');
    expect(titles).toContain('Workbook Pages');
    // Monday items (Isaac Art History, Asher Piano log)
    expect(titles).toContain('Google Classroom');
    expect(titles).toContain('Hand in Piano log');
    // Tuesday items should NOT show on Friday
    expect(titles).not.toContain('Beast Academy Book');
  });

  it('on Saturday (2026-10-24) and Sunday (2026-10-25), shows Monday weekly assignments', () => {
    const satRes = evaluateHomeworkForDate(STARTER_WEEKLY_ITEMS, '2026-10-24');
    const sunRes = evaluateHomeworkForDate(STARTER_WEEKLY_ITEMS, '2026-10-25');

    expect(satRes.tasks.map(t => t.raw_title)).toEqual(['Google Classroom', 'Hand in Piano log']);
    expect(sunRes.tasks.map(t => t.raw_title)).toEqual(['Google Classroom', 'Hand in Piano log']);
  });

  it('generates non-duplicate quick date chips', () => {
    // Thursday Oct 22: Tomorrow IS Friday, so chips should not have two Friday buttons
    const chips = getQuickDateChips('2026-10-22');
    const dates = chips.map(c => c.date);
    expect(new Set(dates).size).toBe(dates.length);
    expect(dates[0]).toBe('2026-10-23'); // Tomorrow (Fri)
    expect(dates).toContain('2026-10-26'); // Monday
  });
});
