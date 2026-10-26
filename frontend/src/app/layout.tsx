"use client";

import React, { useState } from "react";
import "./globals.css";
import { AppProvider } from "@/context/AppContext";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";
import { AuditLedgerModal } from "@/components/ui/AuditLedgerModal";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [auditModalOpen, setAuditModalOpen] = useState(false);

  return (
    <html lang="en">
      <head>
        <title>AICTE FinTrust | Security Deposit & FDR Management Portal (SIH26265)</title>
        <meta
          name="description"
          content="AICTE Security Deposit and Fixed Deposit Receipt Management Portal - Dual-Pass OCR, Field Provenance & Clearance Gate."
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body className="min-h-screen flex flex-col bg-[#F8F9FA] text-slate-900 antialiased font-sans">
        <AppProvider>
          <Navbar onOpenAuditModal={() => setAuditModalOpen(true)} />
          <div className="flex-1 flex overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full">
              {children}
            </main>
          </div>
          <AuditLedgerModal
            isOpen={auditModalOpen}
            onClose={() => setAuditModalOpen(false)}
          />
        </AppProvider>
      </body>
    </html>
  );
}
