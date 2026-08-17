import { WorkerStatus } from "@/components/WorkerStatus";

export const dynamic = "force-dynamic";

export default function WorkerPage() {
  return <div className="mx-auto max-w-5xl space-y-4 px-4 py-8"><h1 className="text-2xl font-bold">Estado del Worker</h1><p className="text-sm text-neutral-500">Resumen de Celery: procesos en ejecución, pendientes y programados.</p><WorkerStatus /></div>;
}
