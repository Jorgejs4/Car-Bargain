"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchMe, logout, type AuthUser } from "@/lib/api";

export function AuthStatus() {
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    if (window.localStorage.getItem("carbargains_token")) fetchMe().then(setUser).catch(() => logout());
  }, []);

  if (!user) return <Link href="/login" className="font-medium text-blue-600 hover:underline">Iniciar sesión</Link>;
  return (
    <button type="button" onClick={() => { logout(); setUser(null); window.location.reload(); }} className="text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100">
      {user.email} · Salir
    </button>
  );
}
