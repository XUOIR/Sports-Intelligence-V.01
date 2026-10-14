import Dashboard from '@/components/Dashboard';
import {authenticated} from '@/lib/auth';
import {redirect} from 'next/navigation';
export const dynamic='force-dynamic';
export default async function Page(){if(!await authenticated())redirect('/login');return <Dashboard/>;}
