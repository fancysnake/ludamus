// This is a proof of concept designed by Gemini 3 we're using to base our design on.

import React, { useState, useEffect, useRef } from 'react';
import { 
  Sword, 
  Users, 
  Calendar, 
  MapPin, 
  Shield, 
  Ghost, 
  Search,
  Terminal,
  Compass,
  Sparkles,
  Crown,
  Skull,
  ChevronRight,
  ArrowLeft,
  Globe,
  Layers,
  MessageCircle,
  X,
  Send,
  Minimize2
} from 'lucide-react';

// --- Mock Data (Hierarchy: Sphere -> Event -> Session) ---
const SPHERES = [
  {
    id: 'sphere_1',
    name: "The Astral Sea Collective",
    description: "A digital haven for high-fantasy enthusiasts and old-school revivalists.",
    type: "Online Community",
    members: "2.4k",
    image: "https://images.unsplash.com/photo-1534447677768-be436bb09401?q=80&w=2094&auto=format&fit=crop",
    events: [
      {
        id: 'evt_1',
        title: "Friday Night One-Shots",
        date: "Fri, Oct 20 • 19:00 EST",
        location: "Discord / FoundryVTT",
        description: "Our weekly gathering for drop-in games. No commitment required.",
        image: "https://images.unsplash.com/photo-1610484826967-09c5720778c7?q=80&w=2070&auto=format&fit=crop",
        sessions: [
          {
            id: 'sess_1',
            title: "Tomb of Annihilation",
            system: "D&D 5e",
            gm: "DungeonMaster_99",
            players: { current: 3, max: 5 },
            tags: ["High Level", "Combat"],
            type: "fantasy",
            description: "The final push into the tomb. Level 10 characters provided.",
            image: "https://images.unsplash.com/photo-1599058945522-28d584b6f0ff?q=80&w=2069&auto=format&fit=crop"
          },
          {
            id: 'sess_2',
            title: "Mork Borg: Rotblack Sludge",
            system: "Mork Borg",
            gm: "DoomSayer",
            players: { current: 1, max: 6 },
            tags: ["OSR", "Lethal"],
            type: "fantasy",
            description: "The world is ending. Let's loot one last dungeon.",
            image: "https://images.unsplash.com/photo-1519074069444-1ba4fff66d16?q=80&w=2574&auto=format&fit=crop"
          }
        ]
      },
      {
        id: 'evt_2',
        title: "Halloween Spooktacular",
        date: "Tue, Oct 31 • 20:00 EST",
        location: "Discord",
        description: "A night of horror games and terror.",
        image: "https://images.unsplash.com/photo-1509248961158-e54f6934749c?q=80&w=2037&auto=format&fit=crop",
        sessions: [
          {
            id: 'sess_3',
            title: "Call of Cthulhu: The Haunting",
            system: "CoC 7e",
            gm: "Lovecraft_Lover",
            players: { current: 4, max: 4 },
            tags: ["Horror", "Mystery"],
            type: "horror",
            description: "Investigate the Corbitt House. Don't lose your mind.",
            image: "https://images.unsplash.com/photo-1518331483807-f6adc0e1ad80?q=80&w=2069&auto=format&fit=crop"
          }
        ]
      }
    ]
  },
  {
    id: 'sphere_2',
    name: "Neo-Tokyo Netrunners",
    description: "Dedicated to cyberpunk, sci-fi, and transhumanist tabletop RPGs.",
    type: "In-Person (Seattle)",
    members: "850",
    image: "https://images.unsplash.com/photo-1555680202-c86f0e12f086?q=80&w=2070&auto=format&fit=crop",
    events: [
      {
        id: 'evt_3',
        title: "Saturday System Crash",
        date: "Sat, Oct 21 • 14:00 PST",
        location: "Raygun Lounge, Seattle",
        description: "In-person meetups for sci-fi fans. Bring your dice.",
        image: "https://images.unsplash.com/photo-1542751371-adc38448a05e?q=80&w=2070&auto=format&fit=crop",
        sessions: [
          {
            id: 'sess_4',
            title: "Lancer: Operation Solstice",
            system: "Lancer",
            gm: "MechWarrior",
            players: { current: 3, max: 4 },
            tags: ["Mecha", "Tactical"],
            type: "scifi",
            description: "Union needs you to hold the line.",
            image: "https://images.unsplash.com/photo-1535030456952-3791b811d806?q=80&w=2069&auto=format&fit=crop"
          },
          {
            id: 'sess_5',
            title: "Blade Runner RPG",
            system: "Free League",
            gm: "Officer_K",
            players: { current: 2, max: 5 },
            tags: ["Investigation", "Noir"],
            type: "scifi",
            description: "Retire the rogue replicants before dawn.",
            image: "https://images.unsplash.com/photo-1480796927426-f609979314bd?q=80&w=2070&auto=format&fit=crop"
          }
        ]
      }
    ]
  }
];

// --- Components ---

const GlitchButton = ({ children, variant = "primary", onClick, className = "" }) => (
  <button
    onClick={onClick}
    className={`
      relative group overflow-hidden px-8 py-4 font-bold uppercase tracking-widest text-xs
      transition-all duration-300 font-marauder
      ${variant === 'primary' 
        ? 'bg-[#c5a059] text-[#0a0908] hover:bg-[#e6c885]' 
        : 'bg-transparent text-[#c5a059] border border-[#c5a059] hover:bg-[#c5a059] hover:text-[#0a0908]'}
      ${className}
    `}
  >
    <span className="relative z-10 flex items-center gap-2 group-hover:animate-shake">
      {children}
    </span>
  </button>
);

const Breadcrumbs = ({ items, onNavigate }) => (
  <div className="flex items-center gap-4 text-2xl md:text-3xl font-marauder text-[#8c8c8c] mb-12 animate-fade-in-right relative z-20">
    {items.map((item, idx) => (
      <React.Fragment key={idx}>
        {idx > 0 && <span className="text-[#3d342b] text-sm">/</span>}
        <button 
          onClick={() => onNavigate(item.view, item.data)}
          className={`hover:text-[#c5a059] transition-all hover:scale-105 ${idx === items.length - 1 ? 'text-[#c5a059]' : ''}`}
          disabled={idx === items.length - 1}
        >
          {item.label}
        </button>
      </React.Fragment>
    ))}
  </div>
);

// Reusable Full Height Gradient with Progressive Blur logic
const CinematicCard = ({ image, children, className = "", onClick, delay }) => (
  <div 
    onClick={onClick}
    style={{ animationDelay: `${delay}ms` }}
    className={`
      group relative w-full cursor-pointer overflow-hidden border border-[#3d342b] animate-fade-in-up bg-[#0c0a09]
      ${className}
    `}
  >
    {/* Background Image */}
    <div className="absolute inset-0 z-0">
        <img 
            src={image} 
            alt="" 
            className="w-full h-full object-cover opacity-60 group-hover:scale-105 transition-all duration-700 ease-out"
        />
    </div>

    {/* Full Height Gradient Overlay with Progressive Darkening */}
    <div className="absolute inset-0 z-10 bg-gradient-to-b from-black/10 via-[#0c0a09]/50 to-[#0c0a09] opacity-90" />
    
    {/* Additional Blur Layer for bottom text readability */}
    <div className="absolute bottom-0 left-0 right-0 h-2/3 bg-gradient-to-t from-[#0c0a09] to-transparent opacity-90 backdrop-blur-[2px] z-10" />

    {/* Content */}
    <div className="relative z-20 h-full">
      {children}
    </div>
    
    {/* Decorative Corners */}
    <div className="absolute top-0 left-0 w-4 h-4 border-t border-l border-[#c5a059] opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-30" />
    <div className="absolute bottom-0 right-0 w-4 h-4 border-b border-r border-[#c5a059] opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-30" />
  </div>
);

const SphereCard = ({ sphere, onClick, delay }) => (
  <CinematicCard image={sphere.image} onClick={onClick} delay={delay} className="h-[500px]">
    <div className="absolute inset-0 p-10 flex flex-col justify-between">
      <div className="flex justify-between items-start">
        <span className="text-xs font-marauder font-bold uppercase tracking-widest text-[#c5a059] border border-[#c5a059]/30 px-3 py-1 backdrop-blur-md bg-black/30">
          {sphere.type}
        </span>
        <div className="flex items-center gap-2 text-[#f0e6d2]">
          <Users className="w-4 h-4" />
          <span className="text-sm font-marauder font-bold tracking-wider">{sphere.members}</span>
        </div>
      </div>

      <div>
        <h3 className="text-6xl font-marauder text-[#f0e6d2] mb-4 group-hover:text-[#c5a059] transition-colors duration-300 leading-[0.85] drop-shadow-lg">
          {sphere.name}
        </h3>
        <p className="text-[#d1d1d1] font-marauder text-xl leading-relaxed max-w-md group-hover:text-white transition-colors drop-shadow-md">
          {sphere.description}
        </p>
      </div>
    </div>
  </CinematicCard>
);

const EventRow = ({ event, onClick, delay }) => (
  <div 
    onClick={onClick}
    style={{ animationDelay: `${delay}ms` }}
    className="group relative h-64 w-full cursor-pointer overflow-hidden border-b border-[#3d342b] animate-fade-in-up"
  >
     {/* Background Image & Gradients */}
    <div className="absolute inset-0 z-0">
        <img src={event.image} className="w-full h-full object-cover opacity-40 group-hover:opacity-60 group-hover:scale-105 transition-all duration-700" alt="" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#0c0a09] via-[#0c0a09]/80 to-transparent" />
    </div>

    <div className="relative z-20 p-8 flex flex-col md:flex-row h-full items-center gap-8">
        <div className="flex-shrink-0 w-full md:w-48 flex flex-col justify-center items-start md:items-center border-l-2 border-[#c5a059] pl-6 md:pl-0 md:border-l-0 md:border-r md:border-[#3d342b] md:pr-8">
            <span className="text-xs font-marauder font-bold text-[#c5a059] uppercase tracking-widest mb-2">Date</span>
            <span className="text-5xl font-marauder text-[#f0e6d2] leading-none mb-1">{event.date.split('•')[0].split(',')[0]}</span>
            <span className="text-sm font-marauder text-[#8c8c8c] tracking-widest">{event.date.split('•')[0].split(',')[1]}</span>
        </div>
        
        <div className="flex-grow pt-2">
            <h4 className="text-4xl font-marauder text-[#f0e6d2] group-hover:text-[#c5a059] transition-colors mb-3 leading-none">
                {event.title}
            </h4>
            <div className="flex items-center gap-6 text-sm font-marauder font-bold text-[#a8a8a8] mb-4 tracking-wide">
                <div className="flex items-center gap-2">
                    <MapPin className="w-4 h-4" />
                    {event.location}
                </div>
                <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4" />
                    {event.sessions.length} Sessions
                </div>
            </div>
            <p className="text-[#d1d1d1] font-marauder text-lg leading-relaxed max-w-2xl opacity-80 group-hover:opacity-100">
                {event.description}
            </p>
        </div>

        <div className="flex items-center pl-4">
            <div className="w-16 h-16 rounded-full border border-[#3d342b] flex items-center justify-center group-hover:border-[#c5a059] group-hover:text-[#c5a059] transition-all duration-300 bg-[#0c0a09]/50 backdrop-blur-sm">
                <Compass className="w-8 h-8" />
            </div>
        </div>
    </div>
  </div>
);

const SessionCard = ({ session, delay }) => (
  <CinematicCard image={session.image} delay={delay} className="h-[600px] flex flex-col">
    <div className="p-8 pt-6 h-full flex flex-col relative z-20">
        {/* Header Tags */}
        <div className="flex justify-between items-start mb-auto">
             <div className="flex items-center gap-2 bg-black/40 backdrop-blur-md px-3 py-1 rounded-sm border border-white/10">
                {session.type === 'fantasy' && <Shield className="w-4 h-4 text-[#c5a059]" />}
                {session.type === 'scifi' && <Terminal className="w-4 h-4 text-cyan-500" />}
                {session.type === 'horror' && <Skull className="w-4 h-4 text-purple-500" />}
                <span className="text-xs font-marauder font-bold uppercase tracking-widest text-white">{session.system}</span>
            </div>
            <div className={`
                px-3 py-1 text-xs font-marauder font-bold uppercase tracking-widest border backdrop-blur-md
                ${session.players.current >= session.players.max 
                ? 'border-red-500/50 text-red-200 bg-red-900/60' 
                : 'border-emerald-500/50 text-emerald-200 bg-emerald-900/60'}
            `}>
                {session.players.current}/{session.players.max} Seats
            </div>
        </div>

        {/* Bottom Content */}
        <div className="mt-auto">
            <h3 className="text-3xl font-marauder text-[#f0e6d2] mb-3 leading-[0.9] group-hover:text-[#c5a059] transition-colors drop-shadow-lg">
                {session.title}
            </h3>
            
            <div className="flex items-center gap-2 text-sm font-marauder text-[#a8a8a8] mb-6 tracking-wider">
                <Crown className="w-4 h-4 text-[#c5a059]" />
                <span className="italic">GM: {session.gm}</span>
            </div>

            <p className="text-lg font-marauder text-[#d1d1d1] mb-8 line-clamp-3 leading-relaxed drop-shadow-md">
                {session.description}
            </p>

            <div className="flex gap-2 mb-8 flex-wrap">
                {session.tags.map(tag => (
                <span key={tag} className="text-[10px] font-marauder font-bold uppercase tracking-wider text-[#d1d1d1] border border-[#3d342b] bg-black/40 px-2 py-1">
                    {tag}
                </span>
                ))}
            </div>

            <button className="w-full py-4 border border-[#3d342b] bg-black/40 backdrop-blur-sm text-[#c5a059] font-marauder font-bold text-sm uppercase tracking-widest hover:bg-[#c5a059] hover:text-black transition-all">
                Reserve Seat
            </button>
        </div>
    </div>
  </CinematicCard>
);

const ChatWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { id: 1, text: "Welcome, traveler. Need help finding a table?", sender: 'bot' }
  ]);
  const [input, setInput] = useState("");

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    setMessages([...messages, { id: Date.now(), text: input, sender: 'user' }]);
    setInput("");
    // Simulating response
    setTimeout(() => {
        setMessages(prev => [...prev, { id: Date.now() + 1, text: "The Tavern Keeper is currently pouring ale. Please wait.", sender: 'bot' }]);
    }, 1000);
  };

  return (
    <div className="fixed bottom-8 right-8 z-50 flex flex-col items-end font-marauder">
      {isOpen && (
        <div className="mb-4 w-80 md:w-96 bg-[#0c0a09] border border-[#3d342b] shadow-2xl animate-fade-in-up flex flex-col overflow-hidden rounded-sm h-[400px]">
          {/* Header */}
          <div className="bg-[#1a1614] p-4 border-b border-[#3d342b] flex justify-between items-center">
            <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-[#4ade80] rounded-full animate-pulse" />
                <span className="text-[#c5a059] uppercase tracking-widest text-sm font-bold">Tavern Chat</span>
            </div>
            <button onClick={() => setIsOpen(false)} className="text-[#8c8c8c] hover:text-white">
                <Minimize2 className="w-4 h-4" />
            </button>
          </div>
          
          {/* Messages */}
          <div className="flex-grow p-4 overflow-y-auto space-y-3 bg-black/50">
            {messages.map(msg => (
                <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`
                        max-w-[80%] p-3 text-sm leading-relaxed
                        ${msg.sender === 'user' 
                            ? 'bg-[#c5a059] text-black border border-[#c5a059]' 
                            : 'bg-[#1a1614] text-[#d1d1d1] border border-[#3d342b]'}
                    `}>
                        {msg.text}
                    </div>
                </div>
            ))}
          </div>

          {/* Input */}
          <form onSubmit={handleSend} className="p-3 bg-[#1a1614] border-t border-[#3d342b] flex gap-2">
            <input 
                type="text" 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Write a missive..."
                className="flex-grow bg-black border border-[#3d342b] p-2 text-[#f0e6d2] text-sm focus:outline-none focus:border-[#c5a059]"
            />
            <button type="submit" className="bg-[#c5a059] text-black p-2 hover:bg-[#e6c885]">
                <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}

      <button 
        onClick={() => setIsOpen(!isOpen)}
        className={`
            w-14 h-14 flex items-center justify-center 
            bg-[#c5a059] text-black border-2 border-[#0c0a09] shadow-[0_0_20px_rgba(197,160,89,0.3)]
            hover:scale-110 transition-transform duration-200
            ${isOpen ? 'rotate-90' : 'rotate-0'}
        `}
      >
        {isOpen ? <X className="w-6 h-6" /> : <MessageCircle className="w-6 h-6" />}
      </button>
    </div>
  );
};

const NoiseOverlay = () => (
  <>
    <div className="fixed inset-0 pointer-events-none z-[1] opacity-[0.04] mix-blend-overlay" 
         style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }}></div>
    <div className="fixed inset-0 pointer-events-none z-[2] bg-[radial-gradient(circle_at_50%_50%,rgba(0,0,0,0),rgba(0,0,0,0.4))]" />
  </>
);

// --- Main Application ---

export default function App() {
  const [view, setView] = useState('spheres'); 
  const [activeSphere, setActiveSphere] = useState(null);
  const [activeEvent, setActiveEvent] = useState(null);

  const navigateToSphere = (sphere) => {
    setActiveSphere(sphere);
    setView('sphere_details');
    window.scrollTo(0,0);
  };

  const navigateToEvent = (event) => {
    setActiveEvent(event);
    setView('event_details');
    window.scrollTo(0,0);
  };

  const navigateHome = () => {
    setView('spheres');
    setActiveSphere(null);
    setActiveEvent(null);
    window.scrollTo(0,0);
  };

  const handleBreadcrumb = (targetView, data) => {
    if (targetView === 'spheres') navigateHome();
    if (targetView === 'sphere_details') navigateToSphere(data);
  };

  const getBreadcrumbs = () => {
    const crumbs = [{ label: 'Spheres', view: 'spheres', data: null }];
    if (activeSphere) crumbs.push({ label: activeSphere.name, view: 'sphere_details', data: activeSphere });
    if (activeEvent) crumbs.push({ label: activeEvent.title, view: 'event_details', data: null });
    return crumbs;
  };

  return (
    <div className="min-h-screen bg-[#0c0a09] font-marauder text-[#f0e6d2] selection:bg-[#c5a059] selection:text-[#000]">
      <style>{`
        /* Import Crimson Text from Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;0,700;1,400;1,600;1,700&display=swap');
        
        /* Redefine .font-marauder to use Crimson Text */
        .font-marauder { 
          font-family: 'Crimson Text', serif; 
        }
        
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeInRight {
          from { opacity: 0; transform: translateX(-10px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-1px); }
          75% { transform: translateX(1px); }
        }

        .animate-fade-in-up { animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards; opacity: 0; }
        .animate-fade-in-right { animation: fadeInRight 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards; opacity: 0; }
        .animate-shake { animation: shake 0.2s linear infinite; }
      `}</style>

      <NoiseOverlay />

      {/* Navigation Bar */}
      <nav className="fixed top-0 w-full z-50 border-b border-[#3d342b] bg-[#0c0a09]/90 backdrop-blur-md h-24">
        <div className="max-w-7xl mx-auto px-6 h-full flex justify-between items-center">
          <div className="flex items-center gap-4 cursor-pointer group" onClick={navigateHome}>
            <div className="relative">
                <Crown className="w-6 h-6 text-[#c5a059] group-hover:scale-110 transition-transform" />
                <div className="absolute inset-0 bg-[#c5a059] blur-md opacity-0 group-hover:opacity-40 transition-opacity" />
            </div>
            <div className="flex flex-col">
              <span className="text-2xl font-marauder font-bold tracking-tight leading-none text-[#f0e6d2]">QUEST</span>
              <span className="text-[10px] font-marauder font-bold tracking-[0.4em] text-[#c5a059] uppercase mt-1">Board</span>
            </div>
          </div>
          <div className="hidden md:flex gap-12 text-xs font-marauder font-bold uppercase tracking-widest text-[#5c5c5c]">
            {['Spheres', 'My Seat', 'Inbox'].map(link => (
                <a key={link} href="#" className="hover:text-[#c5a059] transition-colors relative group">
                    {link}
                    <span className="absolute -bottom-2 left-0 w-0 h-[2px] bg-[#c5a059] group-hover:w-full transition-all duration-300" />
                </a>
            ))}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 pt-40 pb-20 relative z-10 min-h-screen">
        
        <Breadcrumbs items={getBreadcrumbs()} onNavigate={handleBreadcrumb} />

        {/* VIEW: ALL SPHERES (HOME) */}
        {view === 'spheres' && (
          <div>
            <div className="mb-20 animate-fade-in-right max-w-4xl">
              <h1 className="text-8xl md:text-[9rem] font-marauder mb-6 text-[#e5e5e5] leading-[0.8]">
                Explore <span className="text-[#c5a059]">Spheres</span>
              </h1>
              <p className="text-2xl text-[#8c8c8c] font-marauder font-light max-w-2xl leading-relaxed mt-8">
                Join curated communities of roleplayers. Find your tribe, then find your table.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
              {SPHERES.map((sphere, idx) => (
                <SphereCard 
                  key={sphere.id} 
                  sphere={sphere} 
                  onClick={() => navigateToSphere(sphere)} 
                  delay={idx * 100} 
                />
              ))}
            </div>
          </div>
        )}

        {/* VIEW: SPHERE DETAILS (EVENTS LIST) */}
        {view === 'sphere_details' && activeSphere && (
          <div>
            {/* Sphere Header with Image */}
            <div className="relative mb-16 border-b border-[#3d342b] pb-12 animate-fade-in-right rounded-sm overflow-hidden min-h-[400px] flex flex-col justify-end">
              <div className="absolute inset-0 h-full -z-10">
                 <img src={activeSphere.image} className="w-full h-full object-cover opacity-40" alt="" />
                 <div className="absolute inset-0 bg-gradient-to-t from-[#0c0a09] via-[#0c0a09]/60 to-transparent" />
                 <div className="absolute inset-0 bg-gradient-to-r from-[#0c0a09] via-[#0c0a09]/60 to-transparent" />
              </div>

              <div className="relative z-10 pl-4 max-w-4xl">
                <div className="flex items-center gap-3 text-[#c5a059] mb-6">
                    <Globe className="w-4 h-4" />
                    <span className="uppercase tracking-widest font-bold text-xs font-marauder">Sphere Overview</span>
                </div>
                <h1 className="text-7xl md:text-[7rem] font-marauder mb-6 drop-shadow-xl leading-[0.85]">{activeSphere.name}</h1>
                <p className="text-2xl text-[#d1d1d1] font-marauder font-light leading-relaxed drop-shadow-md">{activeSphere.description}</p>
              </div>
            </div>

            <div className="mb-12 flex justify-between items-end">
               <h2 className="text-2xl text-[#f0e6d2] uppercase tracking-widest font-bold font-marauder pl-4 border-l-2 border-[#c5a059]">
                 Upcoming Gatherings
               </h2>
               <GlitchButton variant="outline">Request Event</GlitchButton>
            </div>

            <div className="flex flex-col gap-8">
              {activeSphere.events.map((event, idx) => (
                <EventRow 
                  key={event.id} 
                  event={event} 
                  onClick={() => navigateToEvent(event)}
                  delay={idx * 100} 
                />
              ))}
            </div>
          </div>
        )}

        {/* VIEW: EVENT DETAILS (SESSIONS LIST) */}
        {view === 'event_details' && activeEvent && (
          <div>
             <div className="relative mb-16 bg-[#12100e] border border-[#3d342b] p-10 md:p-16 animate-fade-in-right overflow-hidden group min-h-[300px] flex flex-col justify-center">
                {/* Event Header Image */}
                <div className="absolute inset-0 z-0">
                    <img src={activeEvent.image} className="w-full h-full object-cover opacity-30 group-hover:opacity-40 transition-opacity duration-1000" alt="" />
                    <div className="absolute inset-0 bg-gradient-to-r from-[#0c0a09] via-[#0c0a09]/80 to-transparent" />
                </div>

                <div className="relative z-10 flex flex-col md:flex-row md:justify-between md:items-start gap-12">
                  <div className="flex-grow">
                    <div className="flex items-center gap-3 text-[#c5a059] mb-6">
                      <Calendar className="w-4 h-4" />
                      <span className="uppercase tracking-widest font-bold text-xs font-marauder">Event Manifesto</span>
                    </div>
                    <h1 className="text-6xl md:text-8xl font-marauder mb-6 leading-[0.8] drop-shadow-xl">{activeEvent.title}</h1>
                    <div className="flex flex-col gap-3 text-[#d1d1d1] font-marauder text-xl font-light">
                       <span className="flex items-center gap-2"><span className="w-2 h-2 bg-[#c5a059] rounded-full" /> {activeEvent.date}</span>
                       <span className="flex items-center gap-2"><MapPin className="w-4 h-4" /> {activeEvent.location}</span>
                    </div>
                  </div>
                  <div className="text-right hidden md:block min-w-[200px]">
                     <div className="text-8xl font-marauder text-[#c5a059] mb-2 leading-none">{activeEvent.sessions.length}</div>
                     <div className="text-sm font-bold uppercase tracking-widest text-[#5c5c5c] font-marauder">Active Tables</div>
                  </div>
                </div>
             </div>

             <h2 className="text-2xl text-[#f0e6d2] uppercase tracking-widest font-bold font-marauder mb-12 flex items-center gap-4">
                <span className="w-8 h-[2px] bg-[#c5a059]" />
                Open Tables
             </h2>

             <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                {activeEvent.sessions.map((session, idx) => (
                  <SessionCard key={session.id} session={session} delay={idx * 100} />
                ))}
             </div>
          </div>
        )}

        <ChatWidget />
      </main>
    </div>
  );
}
