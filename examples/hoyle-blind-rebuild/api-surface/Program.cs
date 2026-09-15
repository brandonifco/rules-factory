// The public surface of a compiled .NET engine, as text: every exported type, and every public or
// protected member declared on it, with nullability, default values and constant values, followed by
// the member's public XML documentation. Nothing else. Method bodies are never read: the tool uses
// reflection over metadata, and does not touch IL.
//
//   dotnet run --project ApiSurface.csproj -- --bin DIR --assembly NAME [--assembly NAME ...]
//                                            [--generated DIR ...] --out FILE
//
// --bin is a directory holding the assemblies, everything they reference, and NAME.xml beside each
// NAME.dll. --generated names a directory of *.g.cs files; a type declared in one is marked, since
// the factory writes it and a rebuild produces it rather than writing it.
//
// Output is deterministic: types by namespace then name, members by kind then signature, ordinal.
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Xml.Linq;

var bin = "";
var outPath = "";
var assemblies = new List<string>();
var generatedDirs = new List<string>();
for (int i = 0; i < args.Length; i++)
{
    switch (args[i])
    {
        case "--bin": bin = args[++i]; break;
        case "--out": outPath = args[++i]; break;
        case "--assembly": assemblies.Add(args[++i]); break;
        case "--generated": generatedDirs.Add(args[++i]); break;
        default: Console.Error.WriteLine($"unknown argument {args[i]}"); return 2;
    }
}

if (bin.Length == 0 || outPath.Length == 0 || assemblies.Count == 0)
{
    Console.Error.WriteLine("usage: --bin DIR --assembly NAME [--assembly NAME ...] [--generated DIR ...] --out FILE");
    return 2;
}

var generated = new HashSet<string>(StringComparer.Ordinal);
var declaration = new Regex(@"\b(?:class|record|struct|interface|enum)\s+(?:class\s+|struct\s+)?([A-Z]\w*)", RegexOptions.CultureInvariant);
foreach (var dir in generatedDirs)
{
    foreach (var file in Directory.EnumerateFiles(dir, "*.g.cs", SearchOption.AllDirectories).Order(StringComparer.Ordinal))
    {
        foreach (Match m in declaration.Matches(File.ReadAllText(file)))
        {
            generated.Add(m.Groups[1].Value);
        }
    }
}

var full = Path.GetFullPath(bin);
AppDomain.CurrentDomain.AssemblyResolve += (_, e) =>
{
    var candidate = Path.Combine(full, new AssemblyName(e.Name).Name + ".dll");
    return File.Exists(candidate) ? Assembly.LoadFrom(candidate) : null;
};

var output = new StringBuilder();
output.Append("# Public API contract\n\n");
output.Append("Generated from compiled assemblies by examples/hoyle-blind-rebuild/api-surface: signatures, constant\n");
output.Append("values and public XML documentation only. No method body is read. `[generated]` marks a type the\n");
output.Append("factory's generated code declares (a rebuild produces it; hand-written partial members may be added).\n");

foreach (var name in assemblies)
{
    var assembly = Assembly.LoadFrom(Path.Combine(full, name + ".dll"));
    var docs = Docs.Load(Path.Combine(full, name + ".xml"));
    output.Append($"\n## Assembly {name}\n");
    foreach (var group in assembly.GetExportedTypes().GroupBy(t => t.Namespace ?? "").OrderBy(g => g.Key, StringComparer.Ordinal))
    {
        output.Append($"\n### namespace {group.Key}\n");
        foreach (var type in group.OrderBy(t => Render.TypeName(t, null), StringComparer.Ordinal))
        {
            output.Append('\n');
            output.Append("#### ").Append(Render.TypeHeader(type));
            if (generated.Contains(type.Name.Split('`')[0]))
            {
                output.Append("  [generated]");
            }

            output.Append('\n');
            Docs.Append(output, docs, Ids.Of(type), "");
            foreach (var (signature, id) in Render.Members(type))
            {
                output.Append("\n    ").Append(signature).Append('\n');
                Docs.Append(output, docs, id, "      ");
            }
        }
    }
}

File.WriteAllText(outPath, output.ToString().Replace("\r\n", "\n", StringComparison.Ordinal), new UTF8Encoding(false));
return 0;

internal static class Render
{
    private const BindingFlags Declared = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance
        | BindingFlags.Static | BindingFlags.DeclaredOnly;

    private static readonly NullabilityInfoContext Nullability = new();

    private static readonly Dictionary<Type, string> Aliases = new()
    {
        [typeof(void)] = "void", [typeof(bool)] = "bool", [typeof(byte)] = "byte", [typeof(sbyte)] = "sbyte",
        [typeof(short)] = "short", [typeof(ushort)] = "ushort", [typeof(int)] = "int", [typeof(uint)] = "uint",
        [typeof(long)] = "long", [typeof(ulong)] = "ulong", [typeof(float)] = "float", [typeof(double)] = "double",
        [typeof(decimal)] = "decimal", [typeof(char)] = "char", [typeof(string)] = "string", [typeof(object)] = "object",
    };

    private static bool Visible(MethodBase? m) => m is not null && (m.IsPublic || m.IsFamily || m.IsFamilyOrAssembly);

    private static bool Visible(FieldInfo f) => f.IsPublic || f.IsFamily || f.IsFamilyOrAssembly;

    private static bool CompilerGenerated(MemberInfo m) => m.IsDefined(typeof(CompilerGeneratedAttribute), false);

    private static bool IsRecord(Type t) =>
        t.GetMethod("PrintMembers", Declared, [typeof(StringBuilder)]) is { } p && CompilerGenerated(p);

    public static string TypeName(Type t, NullabilityInfo? n)
    {
        if (t.IsByRef)
        {
            return TypeName(t.GetElementType()!, n);
        }

        if (Nullable.GetUnderlyingType(t) is { } underlying)
        {
            return TypeName(underlying, n?.GenericTypeArguments.FirstOrDefault()) + "?";
        }

        string mark = !t.IsValueType && n?.ReadState == NullabilityState.Nullable ? "?" : "";
        if (t.IsArray)
        {
            return TypeName(t.GetElementType()!, n?.ElementType) + "[]" + mark;
        }

        if (t.IsGenericParameter)
        {
            return t.Name + mark;
        }

        if (Aliases.TryGetValue(t, out var alias))
        {
            return alias + mark;
        }

        string name = t.Name.Split('`')[0];
        if (t.IsNested && !t.IsGenericParameter)
        {
            var outer = t.DeclaringType!;
            if (outer.IsGenericTypeDefinition && t.IsGenericType)
            {
                // A nested type of a generic type carries its parent's arguments first.
                var all = t.GetGenericArguments();
                int own = outer.GetGenericArguments().Length;
                var outerType = outer.MakeGenericType(all[..own]);
                return TypeName(outerType, null) + "." + name + mark;
            }

            name = TypeName(outer, null) + "." + name;
        }

        if (t.IsGenericType)
        {
            var arguments = t.GetGenericArguments();
            int skip = t.IsNested && t.DeclaringType!.IsGenericTypeDefinition ? t.DeclaringType.GetGenericArguments().Length : 0;
            var rendered = arguments.Skip(skip).Select((a, i) => TypeName(a, n?.GenericTypeArguments.ElementAtOrDefault(i + skip)));
            if (arguments.Length > skip)
            {
                name += "<" + string.Join(", ", rendered) + ">";
            }
        }

        return name + mark;
    }

    public static string TypeHeader(Type t)
    {
        var parts = new List<string> { "public" };
        string kind;
        if (t.IsEnum)
        {
            kind = "enum";
        }
        else if (t.IsInterface)
        {
            kind = "interface";
        }
        else if (t.IsValueType)
        {
            kind = IsRecord(t) ? "record struct" : "struct";
            if (t.IsDefined(typeof(IsReadOnlyAttribute), false))
            {
                parts.Add("readonly");
            }
        }
        else if (t.IsSubclassOf(typeof(Delegate)))
        {
            kind = "delegate";
        }
        else
        {
            kind = IsRecord(t) ? "record" : "class";
            if (t.IsAbstract && t.IsSealed)
            {
                parts.Add("static");
            }
            else if (t.IsAbstract)
            {
                parts.Add("abstract");
            }
            else if (t.IsSealed)
            {
                parts.Add("sealed");
            }
        }

        parts.Add(kind);
        string header = string.Join(' ', parts) + " " + TypeName(t, null);
        var bases = new List<string>();
        if (t.IsEnum)
        {
            bases.Add(TypeName(Enum.GetUnderlyingType(t), null));
        }
        else if (!t.IsValueType && !t.IsInterface && t.BaseType is { } b && b != typeof(object))
        {
            bases.Add(TypeName(b, null));
        }

        foreach (var i in t.GetInterfaces().Where(i => !(i.IsGenericType && i.GetGenericTypeDefinition() == typeof(IEquatable<>) && IsRecord(t))
                     && (t.BaseType is null || !t.BaseType.GetInterfaces().Contains(i))).Select(i => TypeName(i, null)).Order(StringComparer.Ordinal))
        {
            bases.Add(i);
        }

        return bases.Count == 0 ? header : header + " : " + string.Join(", ", bases);
    }

    public static IEnumerable<(string Signature, string Id)> Members(Type t)
    {
        var rows = new List<(int Kind, string Signature, string Id)>();
        if (t.IsEnum)
        {
            foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Static).OrderBy(f => Convert.ToInt64(f.GetRawConstantValue(), System.Globalization.CultureInfo.InvariantCulture)))
            {
                rows.Add((0, $"{f.Name} = {f.GetRawConstantValue()}", Ids.Of(f)));
            }

            return rows.Select(r => (r.Signature, r.Id));
        }

        foreach (var f in t.GetFields(Declared).Where(Visible).Where(f => !CompilerGenerated(f)))
        {
            string modifiers = f.IsLiteral ? "const " : (f.IsStatic ? "static " : "") + (f.IsInitOnly ? "readonly " : "");
            string value = f.IsLiteral ? " = " + Literal(f.GetRawConstantValue(), f.FieldType) : "";
            rows.Add((1, $"{Access(f)} {modifiers}{TypeName(f.FieldType, Nullability.Create(f))} {f.Name}{value}", Ids.Of(f)));
        }

        foreach (var c in t.GetConstructors(Declared).Where(c => Visible(c) && !CompilerGenerated(c)))
        {
            if (IsRecord(t) && c.GetParameters() is [{ } only] && only.ParameterType == t)
            {
                continue; // the record's copy constructor
            }

            rows.Add((2, $"{Access(c)} {TypeName(t, null).Split('<')[0]}({Parameters(c)})", Ids.Of(c)));
        }

        foreach (var p in t.GetProperties(Declared))
        {
            var get = p.GetMethod;
            var set = p.SetMethod;
            if (!Visible(get) && !Visible(set))
            {
                continue;
            }

            if (p.Name == "EqualityContract" || CompilerGenerated(p))
            {
                continue;
            }

            var accessor = Visible(get) ? get! : set!;
            string accessors = (Visible(get) ? "get; " : "")
                + (Visible(set) ? (set!.ReturnParameter.GetRequiredCustomModifiers().Contains(typeof(IsExternalInit)) ? "init; " : "set; ") : "");
            string indexer = p.GetIndexParameters().Length > 0 ? "this[" + Parameters(p.GetIndexParameters()) + "]" : p.Name;
            rows.Add((3, $"{Access(accessor)} {(accessor.IsStatic ? "static " : "")}{Virtual(accessor)}{TypeName(p.PropertyType, Nullability.Create(p))} {indexer} {{ {accessors}}}", Ids.Of(p)));
        }

        foreach (var e in t.GetEvents(Declared).Where(e => Visible(e.AddMethod)))
        {
            rows.Add((4, $"{Access(e.AddMethod!)} event {TypeName(e.EventHandlerType!, null)} {e.Name}", Ids.Of(e)));
        }

        foreach (var m in t.GetMethods(Declared).Where(m => Visible(m) && !m.IsSpecialName && !CompilerGenerated(m)))
        {
            if (m.Name is "<Clone>$" || m.Name.Contains('<', StringComparison.Ordinal))
            {
                continue;
            }

            string generic = m.IsGenericMethodDefinition ? "<" + string.Join(", ", m.GetGenericArguments().Select(a => a.Name)) + ">" : "";
            string ret = TypeName(m.ReturnType, Nullability.Create(m.ReturnParameter));
            rows.Add((5, $"{Access(m)} {(m.IsStatic ? "static " : "")}{Virtual(m)}{ret} {m.Name}{generic}({Parameters(m)})", Ids.Of(m)));
        }

        foreach (var m in t.GetMethods(Declared).Where(m => Visible(m) && m.IsSpecialName && m.Name.StartsWith("op_", StringComparison.Ordinal) && !CompilerGenerated(m)))
        {
            rows.Add((6, $"{Access(m)} static {TypeName(m.ReturnType, null)} {m.Name}({Parameters(m)})", Ids.Of(m)));
        }

        return rows.OrderBy(r => r.Kind).ThenBy(r => r.Signature, StringComparer.Ordinal).Select(r => (r.Signature, r.Id));
    }

    private static string Access(MethodBase m) => m.IsPublic ? "public" : "protected";

    private static string Access(FieldInfo f) => f.IsPublic ? "public" : "protected";

    private static string Virtual(MethodInfo m)
    {
        if (m.IsAbstract && !m.DeclaringType!.IsInterface)
        {
            return "abstract ";
        }

        if (m.IsVirtual && !m.IsFinal && !m.DeclaringType!.IsInterface)
        {
            return m.GetBaseDefinition().DeclaringType != m.DeclaringType ? "override " : "virtual ";
        }

        if (m.IsVirtual && m.GetBaseDefinition().DeclaringType != m.DeclaringType)
        {
            return "override ";
        }

        return "";
    }

    private static string Parameters(MethodBase m) => Parameters(m.GetParameters());

    private static string Parameters(ParameterInfo[] parameters) => string.Join(", ", parameters.Select(p =>
    {
        var prefix = new StringBuilder();
        if (p.Position == 0 && p.Member.IsDefined(typeof(ExtensionAttribute), false))
        {
            prefix.Append("this ");
        }

        if (p.IsDefined(typeof(ParamArrayAttribute), false))
        {
            prefix.Append("params ");
        }

        if (p.ParameterType.IsByRef)
        {
            prefix.Append(p.IsOut ? "out " : p.IsIn ? "in " : "ref ");
        }

        string text = $"{prefix}{TypeName(p.ParameterType, Nullability.Create(p))} {p.Name}";
        if (p.HasDefaultValue)
        {
            text += " = " + Literal(p.RawDefaultValue, p.ParameterType);
        }

        return text;
    }));

    private static string Literal(object? value, Type type)
    {
        var target = Nullable.GetUnderlyingType(type) ?? type;
        return value switch
        {
            null => type.IsValueType && Nullable.GetUnderlyingType(type) is null ? "default" : "null",
            string s => "\"" + s.Replace("\\", "\\\\", StringComparison.Ordinal).Replace("\"", "\\\"", StringComparison.Ordinal) + "\"",
            bool b => b ? "true" : "false",
            _ when target.IsEnum => TypeName(target, null) + "." + Enum.GetName(target, value),
            IFormattable f => f.ToString(null, System.Globalization.CultureInfo.InvariantCulture),
            _ => value.ToString() ?? "",
        };
    }
}

internal static class Ids
{
    // XML documentation comment ids (ECMA-334 annex D).
    public static string Of(Type t) => "T:" + TypeId(t);

    public static string Of(FieldInfo f) => "F:" + TypeId(f.DeclaringType!) + "." + f.Name;

    public static string Of(EventInfo e) => "E:" + TypeId(e.DeclaringType!) + "." + e.Name;

    public static string Of(PropertyInfo p)
    {
        var index = p.GetIndexParameters();
        return "P:" + TypeId(p.DeclaringType!) + "." + p.Name + (index.Length == 0 ? "" : "(" + string.Join(",", index.Select(i => ParamId(i.ParameterType))) + ")");
    }

    public static string Of(MethodBase m)
    {
        string name = m is ConstructorInfo ? (m.IsStatic ? "#cctor" : "#ctor") : m.Name;
        if (m is MethodInfo { IsGenericMethodDefinition: true } g)
        {
            name += "``" + g.GetGenericArguments().Length;
        }

        var parameters = m.GetParameters();
        string id = "M:" + TypeId(m.DeclaringType!) + "." + name
            + (parameters.Length == 0 ? "" : "(" + string.Join(",", parameters.Select(p => ParamId(p.ParameterType))) + ")");
        if (m.Name is "op_Implicit" or "op_Explicit" && m is MethodInfo mi)
        {
            id += "~" + ParamId(mi.ReturnType);
        }

        return id;
    }

    private static string TypeId(Type t)
    {
        if (t.IsNested)
        {
            return TypeId(t.DeclaringType!) + "." + t.Name;
        }

        return (t.Namespace is { Length: > 0 } ns ? ns + "." : "") + t.Name;
    }

    private static string ParamId(Type t)
    {
        if (t.IsByRef)
        {
            return ParamId(t.GetElementType()!) + "@";
        }

        if (t.IsArray)
        {
            return ParamId(t.GetElementType()!) + "[" + new string(',', t.GetArrayRank() - 1) + "]";
        }

        if (t.IsGenericParameter)
        {
            return (t.DeclaringMethod is null ? "`" : "``") + t.GenericParameterPosition;
        }

        if (t.IsGenericType)
        {
            string outer = t.IsNested ? ParamIdName(t.DeclaringType!) + "." : (t.Namespace is { Length: > 0 } ns ? ns + "." : "");
            string name = t.Name.Split('`')[0];
            var args = t.GetGenericArguments();
            if (t.IsNested)
            {
                args = args.Skip(t.DeclaringType!.GetGenericArguments().Length).ToArray();
            }

            return outer + name + (args.Length == 0 ? "" : "{" + string.Join(",", args.Select(ParamId)) + "}");
        }

        return ParamIdName(t);
    }

    private static string ParamIdName(Type t) =>
        t.IsNested ? ParamIdName(t.DeclaringType!) + "." + t.Name.Split('`')[0] : (t.Namespace is { Length: > 0 } ns ? ns + "." : "") + t.Name.Split('`')[0];
}

internal static class Docs
{
    public static Dictionary<string, XElement> Load(string path)
    {
        if (!File.Exists(path))
        {
            throw new FileNotFoundException($"no XML documentation beside the assembly: {path}");
        }

        return XDocument.Load(path).Descendants("member")
            .Where(m => m.Attribute("name") is not null)
            .GroupBy(m => m.Attribute("name")!.Value, StringComparer.Ordinal)
            .ToDictionary(g => g.Key, g => g.First(), StringComparer.Ordinal);
    }

    public static void Append(StringBuilder output, Dictionary<string, XElement> docs, string id, string indent)
    {
        if (!docs.TryGetValue(id, out var member))
        {
            return;
        }

        foreach (var section in member.Elements())
        {
            string label = section.Name.LocalName switch
            {
                "summary" => "",
                "remarks" => "Remarks: ",
                "returns" => "Returns: ",
                "value" => "Value: ",
                "param" => $"Parameter {section.Attribute("name")?.Value}: ",
                "typeparam" => $"Type parameter {section.Attribute("name")?.Value}: ",
                "exception" => $"Throws {Cref(section.Attribute("cref")?.Value)}: ",
                "inheritdoc" => "(documentation inherited)",
                _ => section.Name.LocalName + ": ",
            };
            string text = Text(section).Trim();
            foreach (var paragraph in (label + text).Split("\n\n", StringSplitOptions.RemoveEmptyEntries))
            {
                output.Append(indent).Append("/// ").Append(Regex.Replace(paragraph.Trim(), @"[ \t]*\n[ \t]*", "\n" + indent + "/// ")).Append('\n');
            }
        }
    }

    private static string Cref(string? cref) => cref is null ? "" : cref.Length > 2 && cref[1] == ':' ? cref[2..] : cref;

    private static string Text(XElement element)
    {
        var sb = new StringBuilder();
        foreach (var node in element.Nodes())
        {
            switch (node)
            {
                case XText text:
                    sb.Append(Regex.Replace(text.Value, @"\s+", " "));
                    break;
                case XElement e:
                    switch (e.Name.LocalName)
                    {
                        case "see" or "seealso":
                            sb.Append('`').Append(e.Attribute("cref") is { } c ? Cref(c.Value) : e.Attribute("langword")?.Value ?? e.Attribute("href")?.Value ?? Text(e)).Append('`');
                            break;
                        case "paramref" or "typeparamref":
                            sb.Append('`').Append(e.Attribute("name")?.Value).Append('`');
                            break;
                        case "c":
                            sb.Append('`').Append(Text(e)).Append('`');
                            break;
                        case "para":
                            sb.Append("\n\n").Append(Text(e).Trim()).Append("\n\n");
                            break;
                        case "list":
                            sb.Append("\n\n");
                            foreach (var item in e.Elements("item"))
                            {
                                sb.Append("- ").Append(Text(item).Trim()).Append('\n');
                            }

                            sb.Append('\n');
                            break;
                        case "b" or "em" or "i":
                            sb.Append(Text(e));
                            break;
                        default:
                            sb.Append(Text(e));
                            break;
                    }

                    break;
            }
        }

        return Regex.Replace(sb.ToString(), @"\n{3,}", "\n\n");
    }
}
