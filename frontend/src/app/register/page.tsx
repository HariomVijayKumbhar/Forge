'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { ApiError } from '@/lib/api';
import { UserPlus, User, Mail, Lock, Loader2, AlertCircle } from 'lucide-react';

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const trimmedUsername = username.trim();
    const trimmedEmail = email.trim();

    if (trimmedUsername.length < 3) {
      setError('Username must be at least 3 characters.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await register(trimmedUsername, trimmedEmail || undefined, password);
      router.push('/');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 400) {
          setError('Username already exists. Try a different one.');
        } else if (err.status === 429) {
          setError('Rate limit exceeded. Please wait a moment.');
        } else {
          setError(err.message || 'Registration failed. Please try again.');
        }
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const isFormValid =
    !isLoading &&
    username.trim().length >= 3 &&
    password.length >= 6 &&
    password === confirmPassword;

  return (
    <div className='fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-md'>
      <div className='w-full max-w-md glass-panel-glow rounded-2xl p-8 relative overflow-hidden'>
        <div className='absolute -top-24 -left-24 w-48 h-48 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none' />
        <div className='absolute -top-24 -right-24 w-48 h-48 bg-cyan-500/20 rounded-full blur-3xl pointer-events-none' />

        <div className='flex flex-col items-center text-center mb-6'>
          <div className='w-14 h-14 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 mb-4 shadow-inner'>
            <UserPlus className='w-7 h-7' />
          </div>
          <h2 className='text-2xl font-bold text-white tracking-tight'>Create Account</h2>
          <p className='text-sm text-slate-400 mt-1 max-w-xs'>
            Join Forge to access the autonomous agent environment.
          </p>
        </div>

        {error && (
          <div className='mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-start gap-2.5'>
            <AlertCircle className='w-4 h-4 flex-shrink-0 mt-0.5' />
            <span className='flex-1'>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className='space-y-4'>
          <div>
            <label className='block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5'>
              Username
            </label>
            <div className='relative'>
              <input
                type='text'
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder='Choose a username'
                autoFocus
                autoComplete='username'
                disabled={isLoading}
                className='w-full px-4 py-3 rounded-xl bg-surface-100/90 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all pl-10'
              />
              <User className='w-4 h-4 text-slate-400 absolute left-3.5 top-3.5' />
            </div>
          </div>

          <div>
            <label className='block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5'>
              Email <span className='text-slate-500 font-normal'>(optional)</span>
            </label>
            <div className='relative'>
              <input
                type='email'
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder='you@example.com'
                autoComplete='email'
                disabled={isLoading}
                className='w-full px-4 py-3 rounded-xl bg-surface-100/90 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all pl-10'
              />
              <Mail className='w-4 h-4 text-slate-400 absolute left-3.5 top-3.5' />
            </div>
          </div>

          <div>
            <label className='block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5'>
              Password
            </label>
            <div className='relative'>
              <input
                type='password'
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder='Choose a password'
                autoComplete='new-password'
                disabled={isLoading}
                className='w-full px-4 py-3 rounded-xl bg-surface-100/90 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all pl-10'
              />
              <Lock className='w-4 h-4 text-slate-400 absolute left-3.5 top-3.5' />
            </div>
          </div>

          <div>
            <label className='block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5'>
              Confirm Password
            </label>
            <div className='relative'>
              <input
                type='password'
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder='Confirm your password'
                autoComplete='new-password'
                disabled={isLoading}
                className='w-full px-4 py-3 rounded-xl bg-surface-100/90 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all pl-10'
              />
              <Lock className='w-4 h-4 text-slate-400 absolute left-3.5 top-3.5' />
            </div>
          </div>

          <button
            type='submit'
            disabled={!isFormValid}
            className='w-full py-3 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-600 text-white font-medium text-sm flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed group'
          >
            {isLoading ? (
              <>
                <Loader2 className='w-4 h-4 animate-spin' />
                <span>Creating account...</span>
              </>
            ) : (
              <>
                <span>Sign Up</span>
                <UserPlus className='w-4 h-4 group-hover:translate-x-0.5 transition-transform' />
              </>
            )}
          </button>
        </form>

        <div className='mt-6 pt-4 border-t border-white/5 text-center text-xs text-slate-400'>
          <span>Already have an account? </span>
          <a
            href='/login'
            className='text-indigo-400 hover:text-indigo-300 font-medium transition-colors'
          >
            Sign in
          </a>
        </div>
      </div>
    </div>
  );
}
