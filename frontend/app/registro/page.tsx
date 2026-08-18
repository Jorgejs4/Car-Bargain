"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { register } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); try { await register(email, password); router.push("/"); router.refresh(); } catch { setError("No se pudo crear la cuenta. Comprueba el email y que la contraseña tenga al menos 8 caracteres."); } }
  return <div className="mx-auto max-w-md px-4 py-12"><form onSubmit={submit} className="space-y-4 rounded-xl border p-6 dark:border-neutral-800"><h1 className="text-2xl font-bold">Crear cuenta</h1>{error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}<label className="block text-sm">Email<input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border p-2 dark:border-neutral-700 dark:bg-neutral-900" /></label><label className="block text-sm">Contraseña<input required minLength={8} type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border p-2 dark:border-neutral-700 dark:bg-neutral-900" /></label><button className="w-full rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700">Registrarme</button><p className="text-center text-sm text-neutral-500"><Link href="/login" className="text-blue-600 hover:underline">Ya tengo cuenta</Link></p></form></div>;
}
