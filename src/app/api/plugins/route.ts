import { NextRequest, NextResponse } from 'next/server';
import type { Plugin } from '@/types';

const PLUGINS: Plugin[] = [
  {
    id: 'weather-forecast',
    name: 'Weather Forecast',
    description: 'Real-time weather updates and forecasts. Ask AMARA about current conditions, hourly and 7-day outlooks for any location.',
    category: 'Utilities',
    author: 'AMARA Labs',
    version: '2.1.0',
    rating: 4.8,
    installs: 142300,
    tags: ['weather', 'forecast', 'location'],
  },
  {
    id: 'smart-home-control',
    name: 'Smart Home Control',
    description: 'Control lights, thermostats, locks, and other smart devices using voice commands through AMARA.',
    category: 'Smart Home',
    author: 'HomeSync',
    version: '1.4.2',
    rating: 4.6,
    installs: 98700,
    tags: ['smart home', 'iot', 'automation', 'lights', 'thermostat'],
  },
  {
    id: 'calendar-assistant',
    name: 'Calendar Assistant',
    description: 'Schedule meetings, set reminders, and manage your calendar hands-free. Integrates with Google Calendar and Outlook.',
    category: 'Productivity',
    author: 'AMARA Labs',
    version: '3.0.1',
    rating: 4.7,
    installs: 201500,
    tags: ['calendar', 'schedule', 'reminders', 'meetings'],
  },
  {
    id: 'music-player',
    name: 'Music Player',
    description: 'Play music, create playlists, and discover new tracks by mood or genre. Supports Spotify, Apple Music, and local libraries.',
    category: 'Entertainment',
    author: 'SoundBridge',
    version: '2.3.0',
    rating: 4.9,
    installs: 315800,
    tags: ['music', 'spotify', 'playlist', 'audio'],
  },
  {
    id: 'news-briefing',
    name: 'News Briefing',
    description: 'Get personalized news summaries on topics you care about. AMARA reads headlines and key points aloud on demand.',
    category: 'Productivity',
    author: 'InfoStream',
    version: '1.2.3',
    rating: 4.4,
    installs: 76200,
    tags: ['news', 'briefing', 'headlines', 'media'],
  },
  {
    id: 'fitness-tracker',
    name: 'Fitness Tracker',
    description: 'Log workouts, track progress, and get coaching tips. Connects with Apple Health, Fitbit, and Garmin.',
    category: 'Health',
    author: 'PulseAI',
    version: '1.7.0',
    rating: 4.5,
    installs: 54900,
    tags: ['fitness', 'health', 'workout', 'exercise'],
  },
  {
    id: 'recipe-chef',
    name: 'Recipe Chef',
    description: 'Ask AMARA for recipe ideas based on ingredients you have. Step-by-step cooking guidance hands-free.',
    category: 'Utilities',
    author: 'CulinaryAI',
    version: '1.1.0',
    rating: 4.3,
    installs: 38400,
    tags: ['recipes', 'cooking', 'food', 'kitchen'],
  },
  {
    id: 'language-translator',
    name: 'Language Translator',
    description: 'Translate spoken or typed text into 50+ languages in real time. Ideal for travel and multilingual conversations.',
    category: 'Communication',
    author: 'LinguaCore',
    version: '2.0.5',
    rating: 4.7,
    installs: 129000,
    tags: ['translation', 'language', 'multilingual', 'travel'],
  },
  {
    id: 'finance-monitor',
    name: 'Finance Monitor',
    description: 'Check account balances, track spending categories, and get budget alerts through voice queries.',
    category: 'Finance',
    author: 'LedgerAI',
    version: '1.3.1',
    rating: 4.2,
    installs: 43100,
    tags: ['finance', 'budget', 'banking', 'spending'],
  },
  {
    id: 'meditation-guide',
    name: 'Meditation Guide',
    description: 'Guided breathing exercises, mindfulness sessions, and sleep sounds. Customize duration and focus area.',
    category: 'Health',
    author: 'CalmPath',
    version: '1.0.8',
    rating: 4.8,
    installs: 67300,
    tags: ['meditation', 'mindfulness', 'sleep', 'wellness'],
  },
  {
    id: 'task-manager',
    name: 'Task Manager',
    description: 'Create, prioritize, and complete tasks with voice commands. Syncs across devices and integrates with Notion and Todoist.',
    category: 'Productivity',
    author: 'FlowState',
    version: '2.2.0',
    rating: 4.6,
    installs: 112400,
    tags: ['tasks', 'productivity', 'todo', 'notion'],
  },
  {
    id: 'podcast-player',
    name: 'Podcast Player',
    description: 'Discover and listen to podcasts on any topic. Ask AMARA to find episodes by keyword, guest, or show name.',
    category: 'Entertainment',
    author: 'WaveForm',
    version: '1.5.2',
    rating: 4.4,
    installs: 58700,
    tags: ['podcast', 'audio', 'entertainment', 'radio'],
  },
  {
    id: 'sleep-tracker',
    name: 'Sleep Tracker',
    description: 'Analyze sleep patterns, set smart alarms, and receive insights to improve sleep quality over time.',
    category: 'Health',
    author: 'PulseAI',
    version: '1.2.0',
    rating: 4.5,
    installs: 49200,
    tags: ['sleep', 'health', 'alarm', 'wellness'],
  },
  {
    id: 'email-assistant',
    name: 'Email Assistant',
    description: 'Compose, send, and summarize emails by voice. Draft replies, flag important messages, and manage your inbox.',
    category: 'Communication',
    author: 'AMARA Labs',
    version: '2.4.1',
    rating: 4.5,
    installs: 93800,
    tags: ['email', 'communication', 'inbox', 'drafting'],
  },
  {
    id: 'stock-watcher',
    name: 'Stock Watcher',
    description: 'Monitor portfolio performance, get price alerts, and receive market summaries delivered by AMARA on your schedule.',
    category: 'Finance',
    author: 'MarketPulse',
    version: '1.6.0',
    rating: 4.3,
    installs: 35600,
    tags: ['stocks', 'investing', 'finance', 'markets'],
  },
  {
    id: 'movie-recommender',
    name: 'Movie Recommender',
    description: 'Get curated movie and TV show picks based on your taste. AMARA explains why each title matches your preferences.',
    category: 'Entertainment',
    author: 'ScreenAI',
    version: '1.0.3',
    rating: 4.6,
    installs: 72100,
    tags: ['movies', 'tv', 'recommendations', 'streaming'],
  },
];

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get('q')?.toLowerCase().trim() ?? '';
  const category = searchParams.get('category')?.trim() ?? '';

  let results = PLUGINS;

  if (category && category !== 'All') {
    results = results.filter((p) => p.category === category);
  }

  if (query) {
    results = results.filter(
      (p) =>
        p.name.toLowerCase().includes(query) ||
        p.description.toLowerCase().includes(query) ||
        p.tags.some((t) => t.toLowerCase().includes(query)) ||
        p.author.toLowerCase().includes(query) ||
        p.category.toLowerCase().includes(query),
    );
  }

  return NextResponse.json({ plugins: results, total: results.length });
}
