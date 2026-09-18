function Header({ title, subtitle, leftAction, rightAction }) {
  return (
    <div className="bg-primary 
                    text-primary-foreground 
                    px-5 pt-17 pb-9 
                    flex items-center 
                    justify-between">
      <div className="flex items-center gap-3">
        {leftAction && <div>{leftAction}</div>}
        <div>
          <h1 className="text-xl font-bold tracking-tight">{title}</h1>
          {subtitle && <p className="text-xs opacity-70 mt-1.5">{subtitle}</p>}
        </div>
      </div>
      {rightAction && <div>{rightAction}</div>}
    </div>
  );
}

export default Header;
