export default function MobileLayout({ children }) {
  return (
    <div className="min-h-screen bg-slate-100 flex justify-center items-center">
      <main className="w-full max-w-md h-[100dvh] bg-background shadow-2xl overflow-hidden flex flex-col relative">
        {children}
      </main>
    </div>
  );
}
