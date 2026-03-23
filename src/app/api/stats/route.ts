import { NextResponse } from "next/server";
import { dealStore } from "@/lib/dealStore";

export async function GET() {
  const stats = dealStore.getStats();
  return NextResponse.json(stats);
}
